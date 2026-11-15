"""Review, spoken merchant approval and call dispatch without an external dial."""
import asyncio
import copy
import importlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import Campaign, Transaction, VoiceSession
from app.services import voice


@pytest.fixture
def calling(monkeypatch):
    calls={}
    attempts=[]

    def queue(db,campaign_id,simulate=False):
        key='call-'+campaign_id
        if key not in calls:
            calls[key]=SimpleNamespace(id=key,campaign_id=campaign_id,status='queued',customer_name='Kush',
                                       offer_amount=20,minimum_bill=200,accepted=False)
        return calls[key]

    def serialize(call):
        return vars(call).copy()

    def dispatch(db,call_id):
        row=calls[call_id]
        if row.status=='queued':
            attempts.append(call_id)
            row.status='calling'
        return serialize(row)

    telephony=importlib.import_module('app.services.telephony')
    monkeypatch.setattr(telephony,'queue_campaign_call',queue)
    monkeypatch.setattr(telephony,'call_dict',serialize)
    monkeypatch.setattr(telephony,'dispatch_call',dispatch)
    class Unavailable:
        async def chat(self,*args,**kwargs):
            return {'provider':'demo','demo':True,'text':'','error':'Test provider unavailable'}
    monkeypatch.setattr(voice,'SarvamProvider',Unavailable)
    return SimpleNamespace(calls=calls,attempts=attempts)


def ask(db,text='Who has not visited in 14 days?',session_id=None,language='hi-IN'):
    return asyncio.run(voice.chat(db,voice.VoiceChat(text=text,language=language,session_id=session_id)))


def test_comeback_proposal_uses_purchase_dates_and_only_names_configured_recipient(seeded,calling):
    response=ask(seeded)
    context=response['comeback']
    assert context['customer_token']=='PK-0036' and context['customer_name']=='Kush'
    assert context['contact']['days_since_visit']>=14
    assert context['eligible_count']==len(context['eligible_customers'])
    assert context['eligible_count']>1
    assert all(customer['days_since_visit']>=14 for customer in context['eligible_customers'])
    assert str(context['eligible_count']-1) in response['response']
    assert response['proposal']['action']=='send_comeback_offer'
    assert response['proposal']['parameters']['offer_amount']==20
    assert response['proposal']['parameters']['minimum_bill']==200
    assert not calling.calls


@pytest.mark.parametrize('confirmation',['Haan','हाँ','हां जी','Yes please!','हो'])
def test_spoken_approval_launches_exact_reviewed_offer_and_dials_once(seeded,calling,confirmation):
    first=ask(seeded)
    before=seeded.scalar(select(func.count()).select_from(Campaign))
    result=ask(seeded,confirmation,first['session_id'])
    assert result['proposal']['id']==first['proposal']['id']
    assert result['proposal']['status']=='approved'
    assert result['action_result']['campaign']['offer_amount']==20
    assert result['action_result']['campaign']['minimum_bill']==200
    assert result['action_result']['call']['status']=='calling'
    assert len(calling.attempts)==1
    assert seeded.scalar(select(func.count()).select_from(Campaign))==before+1
    receipt_count=len(result['messages'])
    again=ask(seeded,confirmation,first['session_id'])
    assert again['action_result']['campaign']['id']==result['action_result']['campaign']['id']
    assert len(again['messages'])==receipt_count
    assert len(calling.attempts)==1
    assert seeded.scalar(select(func.count()).select_from(Campaign))==before+1


def test_spoken_rejection_never_dials_and_cannot_be_reopened(seeded,calling):
    first=ask(seeded)
    before=seeded.scalar(select(func.count()).select_from(Campaign))
    rejected=ask(seeded,'Nahi',first['session_id'])
    assert rejected['proposal']['status']=='rejected'
    assert rejected['action_result']['status']=='rejected'
    assert not calling.calls
    again=ask(seeded,'Haan',first['session_id'])
    assert again['proposal']['status']=='rejected' and 'action_result' not in again
    assert seeded.scalar(select(func.count()).select_from(Campaign))==before


def test_expired_proposal_and_customer_return_both_prevent_call(seeded,calling):
    first=ask(seeded)
    row=seeded.get(VoiceSession,first['session_id'])
    payload=copy.deepcopy(row.payload)
    payload['proposal']['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    row.payload=payload;seeded.commit()
    with pytest.raises(HTTPException) as expired:
        ask(seeded,'Haan',first['session_id'])
    assert expired.value.status_code==409
    seeded.rollback()
    assert not calling.calls
    fresh=ask(seeded)
    seeded.add(Transaction(merchant_id='sharma-kirana',customer_token='PK-0036',amount=250,gross_profit=55,
                           category='Grocery',created_at=datetime.now(timezone.utc),simulated=True))
    seeded.commit()
    with pytest.raises(HTTPException) as changed:
        ask(seeded,'Haan',fresh['session_id'])
    assert changed.value.status_code==409
    assert not calling.calls
    seeded.rollback()
    checked=ask(seeded)
    assert checked['proposal'] is None and checked['comeback']['contact'] is None


def test_affirmative_without_proposal_cannot_be_promoted_to_action_by_model(seeded,calling,monkeypatch):
    class NeverCalled:
        async def chat(self,*args,**kwargs):
            pytest.fail('An isolated confirmation must not be sent to an intent model')
    monkeypatch.setattr(voice,'SarvamProvider',NeverCalled)
    result=ask(seeded,'Haan')
    assert result['proposal'] is None and not calling.calls


def test_amendment_invalidates_old_proposal_and_haan_only_approves_visible_replacement(seeded,calling):
    first=ask(seeded)
    amendment=ask(seeded,'Yes but change discount to 25 minimum bill 200',first['session_id'])
    assert amendment['proposal']['id']!=first['proposal']['id']
    assert amendment['proposal']['action']=='create_campaign'
    assert amendment['proposal']['parameters']['offer_amount']==25
    result=ask(seeded,'Haan',first['session_id'])
    assert result['action_result']['campaign']['offer_amount']==25
    assert result['action_result']['campaign']['minimum_bill']==200
    assert len(calling.attempts)==1
    with pytest.raises(HTTPException):
        voice.approve(seeded,first['session_id'],first['proposal']['id'],True)


def test_failed_call_receipt_never_claims_the_customer_was_called(seeded,calling,monkeypatch):
    telephony=importlib.import_module('app.services.telephony')
    original=telephony.dispatch_call
    def blocked(db,call_id):
        response=original(db,call_id)
        response['status']='blocked'
        return response
    monkeypatch.setattr(telephony,'dispatch_call',blocked)
    first=ask(seeded,language='en-IN')
    approved=ask(seeded,'yes',first['session_id'],language='en-IN')
    assert 'could not be placed' in approved['response']
    assert approved['proposal']['result']['call']['status']=='blocked'
    assert approved['messages'][-1]['text']==approved['response']


def test_greeting_proactively_proposes_offer_and_spoken_hindi_approves_through_api(client,calling):
    first=client.post('/api/v1/voice/chat',json={'text':'नमस्ते','language':'hi-IN'})
    assert first.status_code==200
    greeting=first.json()
    assert greeting['proposal']['action']=='send_comeback_offer'
    assert 'Kush' in greeting['response'] and '14' in greeting['response']
    assert not calling.attempts
    approved=client.post('/api/v1/voice/chat',json={
        'text':'हाँ','language':'hi-IN','session_id':greeting['session_id']})
    assert approved.status_code==200
    assert approved.json()['proposal']['status']=='approved'
    assert approved.json()['action_result']['call']['status']=='calling'
    assert len(calling.attempts)==1


@pytest.mark.parametrize('utterance',['Namaste!','hello','hi','दुकान कैसी चल रही है?',
                                      'aaj kya karna chahiye','kya karu'])
def test_broad_greetings_offer_a_grounded_next_action(seeded,calling,utterance):
    result=ask(seeded,utterance)
    assert result['proposal']['action']=='send_comeback_offer'
    assert not calling.attempts


def test_greeting_with_explicit_revenue_question_is_not_intercepted(seeded,calling):
    result=ask(seeded,'hi, aaj revenue kitna hua?',language='en-IN')
    assert result['proposal'] is None
    assert 'revenue' in result['response'].lower()
    assert not calling.attempts


@pytest.mark.parametrize('language',['hi-IN','mr-IN','en-IN'])
def test_accepted_call_receipt_uses_actual_reviewed_campaign_amounts(language):
    receipt=voice.call_receipt({'customer_name':'Kush','status':'accepted','accepted':True,
                               'offer_amount':25,'minimum_bill':300},language)
    assert '₹25' in receipt and '₹300' in receipt
    assert '₹20' not in receipt and '₹200' not in receipt
