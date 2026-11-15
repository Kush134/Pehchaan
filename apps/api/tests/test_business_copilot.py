import asyncio
from datetime import timedelta
import httpx
from sqlalchemy import select,func
from app.core.clock import business_today
from app.core.config import settings
from app.models import Product,Inventory,Transaction,TelephonyCall
from app.models.retail import StockBatch,RetailSale
from app.models.sms import SmsNotification
from app.services import telephony,sms,voice
from app.services.retail import seed_retail_demo


def test_product_sales_consume_earliest_expiry_and_preserve_ledger(client,seeded):
    p=seeded.scalar(select(Product).order_by(Product.id));before=p.available_stock
    result=client.post('/api/v1/business/batches',json={'product_id':p.id,'quantity':3,'batch_number':'Fresh','expires_on':(business_today()+timedelta(days=2)).isoformat(),'cost_price':60})
    assert result.status_code==200,result.text
    batch=seeded.get(StockBatch,result.json()['id'])
    sale=client.post('/api/v1/business/sales',json={'items':[{'product_id':p.id,'quantity':2}],'payment_method':'cash'},headers={'Idempotency-Key':'sale-once'})
    assert sale.status_code==200,sale.text
    seeded.expire_all()
    assert seeded.get(StockBatch,batch.id).quantity_remaining==1
    assert seeded.get(Product,p.id).available_stock==before+1
    assert seeded.scalar(select(Inventory).where(Inventory.product_id==p.id)).quantity==before+1
    again=client.post('/api/v1/business/sales',json={'items':[{'product_id':p.id,'quantity':2}],'payment_method':'cash'},headers={'Idempotency-Key':'sale-once'})
    assert again.json()['id']==sale.json()['id']
    tx=seeded.get(Transaction,sale.json()['transaction_id'])
    assert tx.amount==p.selling_price*2
    assert sale.json()['gross_profit']==round(p.selling_price*2-120,2)


def test_expired_stock_oversell_and_price_changes_are_rejected(client,seeded):
    p=seeded.scalar(select(Product).order_by(Product.id))
    assert client.post('/api/v1/business/batches',json={'product_id':p.id,'quantity':2,'batch_number':'Old','expires_on':(business_today()-timedelta(days=1)).isoformat()}).status_code==422
    before=seeded.scalar(select(func.count(Transaction.id)))
    for item in [{'product_id':p.id,'quantity':p.available_stock+1},{'product_id':p.id,'quantity':1,'expected_unit_price':1}]:
        assert client.post('/api/v1/business/sales',json={'items':[item]}).status_code==409
    assert seeded.scalar(select(func.count(Transaction.id)))==before


def test_credit_repayments_invoices_and_no_double_revenue(client,seeded):
    p=seeded.scalar(select(Product).order_by(Product.id));token='PK-0036'
    sale=client.post('/api/v1/business/sales',json={'items':[{'product_id':p.id,'quantity':2}],'customer_token':token,'payment_method':'credit','amount_paid':0}).json()
    balance=sale['total_amount'];before=seeded.scalar(select(func.count(Transaction.id)))
    amount=10
    result=client.post('/api/v1/business/khata/payments',json={'customer_token':token,'amount':amount,'payment_method':'cash'},headers={'Idempotency-Key':'repay-once'})
    assert result.status_code==200,result.text
    assert result.json()['outstanding']==balance-amount
    assert client.post('/api/v1/business/khata/payments',json={'customer_token':token,'amount':amount,'payment_method':'cash'},headers={'Idempotency-Key':'repay-once'}).json()['id']==result.json()['id']
    assert client.post('/api/v1/business/khata/payments',json={'customer_token':token,'amount':balance+1}).status_code==409
    assert seeded.scalar(select(func.count(Transaction.id)))==before
    invoice=client.get('/api/v1/business/sales/'+sale['id']+'/invoice').json()
    assert invoice['outstanding']==balance-amount
    assert client.get('/api/v1/business/sales/'+sale['id']+'/invoice.html').status_code==200
    draft=client.post('/api/v1/business/whatsapp/draft',json={'purpose':'invoice','sale_id':sale['id']}).json()
    assert draft['delivery_status']=='draft' and draft['url'].startswith('https://wa.me/')


def test_weekly_evidence_expiry_and_expenses(client,seeded):
    seed_retail_demo(seeded);seeded.commit()
    result=client.get('/api/v1/business/summary?days=7')
    assert result.status_code==200,result.text
    summary=result.json()
    assert summary['best_sellers'] and summary['inventory']['expiring']
    assert summary['sales']['line_item_sales']>0 and summary['health']['score'] is not None
    assert not summary['wait_times']['available']
    assert len(summary['forecast']['daily'])==7
    assert client.post('/api/v1/business/expenses',json={'category':'Transport','amount':50,'description':'Delivery cost','incurred_on':business_today().isoformat()}).status_code==200
    changed=client.get('/api/v1/business/summary?days=7').json()
    assert changed['sales']['expenses']==50
    assert changed['sales']['net_profit']==round(changed['sales']['gross_profit']-50,2)


def test_voice_sale_review_then_haan_records_once(client,seeded,monkeypatch):
    class NoModel:
        async def chat(self,*args,**kwargs):raise AssertionError('Business intents do not need a live LLM')
    monkeypatch.setattr(voice,'SarvamProvider',NoModel)
    first=client.post('/api/v1/voice/chat',json={'text':'2 kilo chawal aur 1 packet biscuit becha','language':'hi-IN'}).json()
    assert first['proposal']['action']=='create_sale',first
    before=seeded.scalar(select(func.count(RetailSale.id)))
    approved=client.post('/api/v1/voice/chat',json={'text':'Haan','session_id':first['session_id'],'language':'hi-IN'})
    assert approved.status_code==200,approved.text
    assert approved.json()['proposal']['status']=='approved'
    assert seeded.scalar(select(func.count(RetailSale.id)))==before+1
    assert client.post('/api/v1/voice/chat',json={'text':'Haan','session_id':first['session_id'],'language':'hi-IN'}).status_code==200
    assert seeded.scalar(select(func.count(RetailSale.id)))==before+1


def test_csv_import_rolls_back_on_invalid_stock(client,seeded):
    p=seeded.scalar(select(Product).order_by(Product.id));before=p.available_stock
    csv=f'invoice_id,product_id,quantity\nTEST1,{p.id},1\nTEST2,{p.id},100000\n'
    response=client.post('/api/v1/business/sales/import',files={'file':('sales.csv',csv,'text/csv')})
    assert response.status_code==409,response.text
    seeded.expire_all();assert seeded.get(Product,p.id).available_stock==before


def test_sms_trial_is_blocked_and_simulation_does_not_send(client,seeded,monkeypatch):
    monkeypatch.setattr(settings,'notification_channel','sms');monkeypatch.setattr(settings,'twilio_sms_trial',True)
    monkeypatch.setattr(sms.httpx,'post',lambda *a,**k:(_ for _ in ()).throw(AssertionError('No SMS on trial or simulator')))
    blocked=client.post('/api/v1/sms/demo-offer',json={'simulate':False}).json()['notification']
    assert blocked['status']=='blocked' and 'trial' in blocked['error']
    assert client.post('/api/v1/sms/notifications/'+blocked['id']+'/simulate-accept').status_code==409
    preview=client.post('/api/v1/sms/demo-offer',json={'simulate':True}).json()['notification']
    assert 'Rs 20 off' in preview['message']
    accepted=client.post('/api/v1/sms/notifications/'+preview['id']+'/simulate-accept')
    assert accepted.status_code==200 and accepted.json()['accepted']
    assert client.post('/api/v1/checkout/quote',json={'customer_token':preview['customer_token'],'bill_amount':250}).json()['payable_amount']==230
