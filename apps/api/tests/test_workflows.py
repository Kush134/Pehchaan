import asyncio
import copy
import io
import wave
from datetime import date,timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.database.seed import seed_demo
from app.models import NegotiationSession,BulkOrder,PolicyDecision,Campaign,PaymentSimulation,Seller
from app.services import negotiation,payments,voice
from app.api.workflows import validate_document,audio_duration


class DemoProvider:
    async def chat(self,*args,**kwargs):
        return {'text':'','provider':'demo','demo':True,'error':'Test provider unavailable.'}


@pytest.fixture
def workflow_db(tmp_path,monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'workflows.db'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr(negotiation,'SessionLocal',factory)
    monkeypatch.setattr(negotiation,'SarvamProvider',DemoProvider)
    monkeypatch.setattr(voice,'SarvamProvider',DemoProvider)
    with factory() as db:
        seed_demo(db);db.commit()
        yield db
    engine.dispose()


async def complete_negotiation(db):
    session=negotiation.create_session(db,negotiation.BuyerRequirement(delivery_date=date.today()+timedelta(days=5)))
    row=db.get(NegotiationSession,session['id']);row.status='running';db.commit()
    await negotiation.run_session(session['id'])
    db.expire_all()
    return db.get(NegotiationSession,session['id'])


@pytest.mark.asyncio
async def test_actual_langgraph_four_rounds_and_private_policies(workflow_db):
    row=await complete_negotiation(workflow_db)
    assert row.status=='awaiting_approval'
    result=negotiation.serialize(row)
    assert result['round_number']==4
    assert len(result['rounds'])==4
    assert all(len(round['quotes'])==3 for round in result['rounds'])
    assert 0<result['best_deal']['total_amount']<=result['budget']
    assert '_mandate' not in result and '_signature' not in result
    assert 'floor' not in str(result).lower()
    assert workflow_db.scalar(select(func.count()).select_from(PolicyDecision))>=12
    assert result['provider']=='demo' and 'unavailable' in result['provider_error']


@pytest.mark.asyncio
async def test_approval_and_payment_lifecycle_is_idempotent(workflow_db):
    db=workflow_db;row=await complete_negotiation(db)
    with pytest.raises(HTTPException) as error:
        payments.confirm_session(db,row.id,merchant_approved=True,buyer_confirmed=False)
    assert error.value.status_code==403
    assert db.scalar(select(func.count()).select_from(BulkOrder))==0
    order=payments.confirm_session(db,row.id,merchant_approved=True,buyer_confirmed=True)
    again=payments.confirm_session(db,row.id,merchant_approved=True,buyer_confirmed=True)
    assert order['id']==again['id']
    assert order['payment_state']=='DELIVERY_CONFIRMATION_PENDING' and order['simulated']
    assert workflow_db.scalar(select(func.count()).select_from(PaymentSimulation))==1
    with pytest.raises(HTTPException): payments.transition(db,order['id'],'release')
    with pytest.raises(HTTPException): payments.transition(db,order['id'],'delivery-confirm',True)
    payments.transition(db,order['id'],'packed')
    with pytest.raises(HTTPException): payments.transition(db,order['id'],'delivery-confirm',False)
    eligible=payments.transition(db,order['id'],'delivery-confirm',True)
    assert eligible['payment_state']=='SETTLEMENT_ELIGIBLE'
    released=payments.transition(db,order['id'],'release')
    assert released['payment_state']=='RELEASED_SIMULATED'
    assert payments.transition(db,order['id'],'release')['timeline']==released['timeline']
    assert 'Paytm' in released['payment_notice'] and 'SIMULATED' in released['payment_notice']


@pytest.mark.asyncio
async def test_persisted_mandate_tamper_is_rejected(workflow_db):
    db=workflow_db;row=await complete_negotiation(db)
    changed=copy.deepcopy(row.payload);changed['budget']=999999;row.payload=changed;db.commit()
    with pytest.raises(HTTPException) as error:
        payments.confirm_session(db,row.id,merchant_approved=True,buyer_confirmed=True)
    assert error.value.status_code==409
    assert db.scalar(select(func.count()).select_from(BulkOrder))==0


@pytest.mark.asyncio
async def test_voice_change_needs_separate_explicit_approval(workflow_db):
    db=workflow_db
    initial_active=db.scalar(select(func.count()).select_from(Campaign).where(Campaign.status=='active'))
    first=await voice.chat(db,voice.VoiceChat(text='Create discount campaign ₹20 on minimum bill ₹300',language='hi-IN'))
    assert first['proposal']['parameters']['offer_amount']==20
    assert db.scalar(select(func.count()).select_from(Campaign).where(Campaign.status=='active'))==initial_active
    second=await voice.chat(db,voice.VoiceChat(text='₹15 discount and ₹250 minimum bill',language='mr-IN',session_id=first['session_id']))
    assert second['proposal']['parameters']['offer_amount']==15
    assert second['proposal']['parameters']['minimum_bill']==250
    with pytest.raises(HTTPException): voice.approve(db,second['session_id'],first['proposal']['id'],True)
    approved=voice.approve(db,second['session_id'],second['proposal']['id'],True)
    assert approved['campaign']['status']=='active'
    assert voice.approve(db,second['session_id'],second['proposal']['id'],True)['campaign']['id']==approved['campaign']['id']
    assert approved['campaign']['stats']['allocated']>0


def test_upload_validation_and_thirty_second_limit():
    with pytest.raises(HTTPException): validate_document(b'not an image','image/jpeg')
    with pytest.raises(HTTPException): validate_document(b'executable','application/octet-stream')
    with pytest.raises(HTTPException): validate_document(b'not a PDF','application/pdf')
    raw=io.BytesIO()
    with wave.open(raw,'wb') as recording:
        recording.setnchannels(1);recording.setsampwidth(2);recording.setframerate(8000)
        recording.writeframes(b'\0\0'*8000*31)
    with pytest.raises(HTTPException) as error: audio_duration(raw.getvalue(),'.wav')
    assert error.value.status_code==422
    assert '30 seconds' in error.value.detail


def test_unknown_and_duplicate_basket_items_rejected(workflow_db):
    with pytest.raises(HTTPException): negotiation.create_session(workflow_db,negotiation.BuyerRequirement(items=[{'product_id':'unknown','quantity':2}]))
    with pytest.raises(HTTPException): negotiation.create_session(workflow_db,negotiation.BuyerRequirement(items=[{'product_id':'rice','quantity':2},{'product_id':'rice','quantity':3}]))


def test_optimizer_excludes_cheap_late_or_unavailable_suppliers(workflow_db):
    state={'items':copy.deepcopy(negotiation.DEFAULT_ITEMS),'budget':40000,'round_number':4,
           'delivery_date':(date.today()+timedelta(days=5)).isoformat()}
    quotes=[negotiation.quote_for(s,state,'Test authorized quote') for s in negotiation.SELLERS]
    for quote in quotes: quote['status']='eligible'
    state['quotes']=quotes
    initial=negotiation.optimize_bundle(state)
    assert initial and initial['total_amount']<=40000
    # Make the cheapest-looking supplier infeasible: it must never win on price alone.
    quotes[2]['delivery_date']=(date.today()+timedelta(days=20)).isoformat()
    for product in quotes[2]['products']: product['unit_price']=.01;product['total']=.01
    filtered=negotiation.optimize_bundle(state)
    assert filtered and all(p['seller_id']!='seller-c' for p in filtered['products'])
    # A stock outage across all sellers leaves no eligible bundle.
    for seller in workflow_db.scalars(select(Seller)):
        seller.payload={**seller.payload,'available_stock':{key:0 for key in negotiation.PRODUCTS}}
    workflow_db.commit()
    assert negotiation.optimize_bundle(state) is None


def test_session_create_idempotency_and_role_permissions(client):
    payload={'requirement':'Office grocery basket','budget':40000}
    first=client.post('/api/v1/haggle/sessions',json=payload,headers={'Idempotency-Key':'basket-one'})
    second=client.post('/api/v1/haggle/sessions',json=payload,headers={'Idempotency-Key':'basket-one'})
    assert first.status_code==200 and second.json()['id']==first.json()['id']
    changed=client.post('/api/v1/haggle/sessions',json={**payload,'budget':35000},headers={'Idempotency-Key':'basket-one'})
    assert changed.status_code==409
    assert client.post('/api/v1/orders/unknown/release',headers={'X-Demo-Role':'buyer'}).status_code==403
    assert client.get('/api/v1/haggle/sessions/any/events',headers={'Last-Event-ID':'invalid'}).status_code==422


@pytest.mark.asyncio
async def test_voided_order_cannot_return_to_settlement(workflow_db):
    db=workflow_db;row=await complete_negotiation(db)
    order=payments.confirm_session(db,row.id,merchant_approved=True,buyer_confirmed=True)
    payments.transition(db,order['id'],'packed')
    voided=payments.transition(db,order['id'],'void')
    assert voided['payment_state']=='VOIDED_SIMULATED'
    with pytest.raises(HTTPException): payments.transition(db,order['id'],'delivery-confirm',True)
    with pytest.raises(HTTPException): payments.transition(db,order['id'],'release')
