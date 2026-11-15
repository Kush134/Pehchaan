"""Durable SMS offers. Delivery, acceptance and payment are separate facts."""
from datetime import datetime,timezone
from urllib.parse import quote
import httpx
from fastapi import HTTPException
from sqlalchemy import select,update
from app.core.config import settings
from app.core.clock import business_today
from app.models import TelephonyCall,Campaign
from app.models.sms import SmsNotification
from app.services import telephony
from app.services.events import emit

TRIAL_NOTICE='Twilio trial supports predefined SMS templates only. Upgrade Messaging to send the custom Rs 20 off Rs 200 offer, then set TWILIO_SMS_TRIAL=false and configure an SMS sender.'

def configuration():
    missing=[]
    for name in ['twilio_account_sid','twilio_auth_token','telephony_public_base_url','telephony_webhook_secret']:
        if not getattr(settings,name):missing.append(name.upper())
    if not settings.twilio_sms_from_number and not settings.twilio_messaging_service_sid:missing.append('TWILIO_SMS_FROM_NUMBER or TWILIO_MESSAGING_SERVICE_SID')
    if not settings.sms_enabled:missing.append('SMS_ENABLED')
    if settings.twilio_sms_trial:missing.append('Twilio custom SMS trial restriction')
    if bool(settings.twilio_api_key_sid)!=bool(settings.twilio_api_key_secret):missing.append('Complete TWILIO_API_KEY_SID and TWILIO_API_KEY_SECRET')
    return {'configured':not missing,'enabled':settings.sms_enabled,'channel':'sms','provider':'twilio','missing':missing,'trial':settings.twilio_sms_trial,'notice':TRIAL_NOTICE if settings.twilio_sms_trial else 'SMS delivery is confirmed only by a signed provider callback.','customer_name':settings.telephony_demo_customer_name,'customer_token':settings.telephony_demo_customer_token,'masked_phone':telephony.masked_phone(settings.telephony_demo_phone),'simulation_available':True}

def offer_url(id):return telephony.public_url('/o/'+id+'?token='+telephony.capability(id,'sms-accept'))

def serialize(db,row):
    offer=db.get(TelephonyCall,row.id)
    return {'id':row.id,'campaign_id':row.campaign_id,'customer_name':offer.customer_name,'customer_token':offer.customer_token,'masked_phone':telephony.masked_phone(offer.phone),'status':row.status,'message':row.body,'simulated':row.simulated,'error':row.error,'accepted':offer.accepted,'acceptance_source':offer.acceptance_source,'redeemed':offer.redeemed,'offer_amount':offer.offer_amount,'minimum_bill':offer.minimum_bill,'created_at':row.created_at.isoformat(),'updated_at':row.updated_at.isoformat(),'channel':'sms'}

def queue(db,campaign_id,simulate=False):
    campaign=db.get(Campaign,campaign_id)
    if not campaign or campaign.status!='active':raise HTTPException(409,'Start an active campaign first')
    existing=db.scalar(select(SmsNotification).where(SmsNotification.campaign_id==campaign_id))
    if existing:
        if existing.simulated!=simulate:raise HTTPException(409,'Use a new campaign for a separate simulated notification')
        return db.get(TelephonyCall,existing.id)
    offer=telephony.queue_campaign_call(db,campaign_id)
    if offer.accepted or offer.redeemed:raise HTTPException(409,'This offer is already accepted or redeemed')
    offer.provider='sms-simulation' if simulate else 'twilio-sms';offer.status='sms_pending';offer.error=None
    body=f'Hi {offer.customer_name}! Get Rs {offer.offer_amount:g} off on a bill of Rs {offer.minimum_bill:g} or more. Visit Sharma Kirana Store now and grab the offer.'
    if settings.telephony_public_base_url:body+=' Accept: '+offer_url(offer.id)
    offer.script=body
    conf=configuration()
    row=SmsNotification(id=offer.id,campaign_id=campaign_id,body=body,simulated=simulate,status='simulated' if simulate else ('queued' if conf['configured'] else 'blocked'),error=None if simulate or conf['configured'] else (TRIAL_NOTICE if settings.twilio_sms_trial else 'Missing: '+', '.join(conf['missing'])))
    db.add(row);db.flush();emit(db,'sms.'+row.status,'Offer SMS '+row.status,'Explicit local preview; no SMS sent.' if simulate else (row.error or 'Notification queued.'),agent='comeback',data={'notification_id':row.id,'campaign_id':campaign_id})
    return offer

def dispatch(db,id):
    row=db.scalar(select(SmsNotification).where(SmsNotification.id==id).with_for_update())
    if not row:raise HTTPException(404,'SMS notification not found')
    if row.simulated or row.status not in {'queued','blocked'}:return serialize(db,row)
    conf=configuration()
    if not conf['configured']:
        row.status='blocked';row.error=TRIAL_NOTICE if settings.twilio_sms_trial else 'Missing: '+', '.join(conf['missing']);db.commit();return serialize(db,row)
    offer=db.get(TelephonyCall,id)
    if offer.phone!=settings.telephony_demo_phone:raise HTTPException(409,'Configured recipient changed. Create a fresh notification.')
    campaign=db.get(Campaign,row.campaign_id)
    if not campaign or campaign.status!='active' or not campaign.start_date<=business_today().isoformat()<=campaign.end_date:raise HTTPException(409,'Campaign is no longer active')
    claim=db.execute(update(SmsNotification).where(SmsNotification.id==id,SmsNotification.status.in_(['queued','blocked'])).values(status='sending',error=None));db.commit();db.refresh(row)
    if not claim.rowcount:return serialize(db,row)
    payload={'To':offer.phone,'Body':row.body,'StatusCallback':telephony.public_url('/api/v1/sms/webhooks/status/'+id)}
    if settings.twilio_messaging_service_sid:payload['MessagingServiceSid']=settings.twilio_messaging_service_sid
    else:payload['From']=settings.twilio_sms_from_number
    try:
        r=httpx.post('https://api.twilio.com/2010-04-01/Accounts/'+quote(settings.twilio_account_sid,safe='')+'/Messages.json',data=payload,auth=telephony.twilio_rest_auth(),timeout=25)
        r.raise_for_status();sid=r.json().get('sid')
        if not isinstance(sid,str) or not sid.startswith(('SM','MM')):raise ValueError('Missing message SID')
        db.refresh(row)
        if row.provider_sid and row.provider_sid!=sid:raise ValueError('Message SID mismatch')
        row.provider_sid=sid
        if row.status=='sending':row.status='submitted'
    except httpx.HTTPStatusError as e:
        db.refresh(row)
        if row.status in {'sending','submitted'}:
            row.status='failed' if e.response.status_code<500 else 'unknown'
            try:code=e.response.json().get('code')
            except ValueError:code=None
            row.error=TRIAL_NOTICE if code==572006 else f'Twilio SMS rejected the request (HTTP {e.response.status_code}, code {code}). Review the SMS sender, destination verification and Messaging permissions.'
    except (httpx.TimeoutException,httpx.TransportError):
        db.refresh(row)
        if row.status=='sending':row.status='unknown';row.error='SMS submission response was lost. Check Twilio Messaging logs; no automatic resend.'
    except Exception:
        db.refresh(row)
        if row.status=='sending':row.status='unknown';row.error='Twilio did not return a usable message identifier. Check Messaging logs before resending.'
    emit(db,'sms.'+row.status,'Offer SMS '+row.status,row.error or 'Awaiting signed delivery receipt.',agent='comeback',data={'notification_id':row.id})
    db.commit();return serialize(db,row)

def accept(db,row,simulation=False):
    if row.simulated!=simulation:raise HTTPException(409,'Simulation cannot accept a live SMS offer')
    offer=db.scalar(select(TelephonyCall).where(TelephonyCall.id==row.id).with_for_update())
    campaign=db.get(Campaign,row.campaign_id)
    if not campaign or campaign.status!='active' or not campaign.start_date<=business_today().isoformat()<=campaign.end_date:raise HTTPException(409,'Offer has expired or is stopped')
    if not simulation and (not row.provider_sid or row.status in {'failed','undelivered','blocked','unknown'}):raise HTTPException(409,'This SMS was not successfully submitted')
    if not offer.accepted:
        offer.accepted=True;offer.accepted_at=datetime.now(timezone.utc);offer.acceptance_source='simulation' if simulation else 'live_sms';offer.status='accepted'
        emit(db,'sms.accepted','Customer accepted SMS offer','Local simulator acceptance.' if simulation else 'Customer explicitly accepted through the signed offer link.',agent='comeback',data={'notification_id':row.id,'accepted':True})
    db.flush();return serialize(db,row)
