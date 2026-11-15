import hmac,html
from datetime import timedelta
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,ConfigDict
from sqlalchemy import select
from app.api.core import merchant_role,mutate
from app.database.session import get_db
from app.models import Campaign
from app.models.sms import SmsNotification
from app.services import sms,telephony
from app.services.campaigns import create_campaign
from app.core.clock import business_today
from app.core.config import settings

router=APIRouter()
public_router=APIRouter()
class DemoInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    simulate:bool=False

@router.get('/sms/status')
def status():return sms.configuration()

@router.get('/sms/notifications')
def notifications(limit:int=Query(50,ge=1,le=100),db=Depends(get_db)):
    return {'items':[sms.serialize(db,r) for r in db.scalars(select(SmsNotification).order_by(SmsNotification.created_at.desc()).limit(limit))]}

@router.post('/sms/demo-offer',dependencies=[Depends(merchant_role)])
def demo(body:DemoInput,request:Request,db=Depends(get_db)):
    def run():
        today=business_today()
        c=create_campaign(db,{'name':'Kush SMS · Rs 20 off Rs 200','target_segment':'All','offer_amount':20,'minimum_bill':200,'start_date':today.isoformat(),'end_date':(today+timedelta(days=7)).isoformat(),'budget':200,'max_customers':1,'language':'en-IN','ab_test':False})
        db.get(Campaign,c['id']).status='active';db.flush()
        offer=sms.queue(db,c['id'],body.simulate);return {'id':offer.id}
    result=mutate(db,request,body.model_dump(),run)
    return {'notification':sms.dispatch(db,result['id'])}

@router.post('/sms/notifications/{id}/simulate-accept',dependencies=[Depends(merchant_role)])
def simulate_accept(id:str,db=Depends(get_db)):
    row=db.scalar(select(SmsNotification).where(SmsNotification.id==id).with_for_update())
    if not row:raise HTTPException(404,'SMS notification not found')
    result=sms.accept(db,row,True);db.commit();return result

@public_router.post('/api/v1/sms/webhooks/status/{id}')
async def delivery(id:str,request:Request,db=Depends(get_db)):
    form=await request.form()
    if not telephony.validate_twilio_signature(telephony.public_url(request.url.path),form,request.headers.get('X-Twilio-Signature','')):raise HTTPException(403,'Invalid Twilio signature')
    row=db.scalar(select(SmsNotification).where(SmsNotification.id==id).with_for_update())
    if not row or row.simulated:raise HTTPException(404,'Live SMS not found')
    if form.get('AccountSid')!=settings.twilio_account_sid:raise HTTPException(403,'Account mismatch')
    sid=form.get('MessageSid') or form.get('SmsSid')
    if not sid or (row.provider_sid and row.provider_sid!=sid):raise HTTPException(409,'Message mismatch')
    if not row.provider_sid:
        if row.status!='sending':raise HTTPException(409,'This SMS was not submitted')
        row.provider_sid=sid
    incoming=form.get('MessageStatus') or form.get('SmsStatus')
    ranks={'sending':0,'submitted':1,'accepted':1,'queued':1,'sent':2,'delivered':3}
    if row.status not in {'delivered','undelivered','failed'} and (incoming in {'failed','undelivered'} or ranks.get(incoming,-1)>ranks.get(row.status,-1)):
        row.status=incoming
        if incoming in {'failed','undelivered'}:row.error='Twilio reported SMS '+incoming+' (code '+str(form.get('ErrorCode','unknown'))+').' 
        from app.services.events import emit
        emit(db,'sms.'+row.status,'SMS '+row.status,'Signed Twilio delivery update.',agent='comeback',data={'notification_id':id})
    db.commit();return {'received':True}

def authorized_offer(db,id,token):
    if not settings.telephony_webhook_secret or not hmac.compare_digest(token,telephony.capability(id,'sms-accept')):raise HTTPException(403,'Invalid offer link')
    row=db.get(SmsNotification,id)
    if not row:raise HTTPException(404,'Offer not found')
    return row

@public_router.get('/o/{id}',response_class=HTMLResponse)
def offer_page(id:str,token:str='',db=Depends(get_db)):
    row=authorized_offer(db,id,token);data=sms.serialize(db,row)
    return HTMLResponse('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Your kirana offer</title><style>body{font:18px system-ui;max-width:520px;margin:50px auto;padding:24px;color:#123359}button{padding:16px;background:#0769b5;color:white;border:0;border-radius:10px;font-size:18px}</style><h1>Sharma Kirana Store</h1><h2>Rs '+str(data['offer_amount'])+' off your next visit</h2><p>Spend Rs '+str(data['minimum_bill'])+' or more. One eligible purchase, while the campaign is active.</p><form method="post"><input type="hidden" name="token" value="'+html.escape(token,quote=True)+'"><button type="submit">Accept this offer</button></form><p>Checkout in this application is simulated; no money is charged here.</p></html>',headers={'Referrer-Policy':'no-referrer','Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"})

@public_router.post('/o/{id}',response_class=HTMLResponse)
async def accept_offer(id:str,request:Request,db=Depends(get_db)):
    form=await request.form();row=authorized_offer(db,id,str(form.get('token','')))
    sms.accept(db,row,False);db.commit()
    return HTMLResponse('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Offer accepted</title><h1>Offer accepted</h1><p>Your discount is saved. Visit Sharma Kirana Store. The merchant dashboard now shows your acceptance.</p></html>',headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
