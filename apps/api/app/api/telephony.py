import base64
import hmac
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, func

from app.api.core import merchant_role
from app.core.clock import business_today
from app.core.config import settings
from app.database.session import get_db
from app.models import TelephonyCall, Campaign
from app.services.events import emit
from app.services.campaigns import create_campaign, launch_campaign
from app.services.idempotency import execute_once
from app.services import telephony

router = APIRouter()


class NotifyRequest(BaseModel):
    simulate: bool = False


class SimulateRequest(BaseModel):
    digit: Literal['1', '2'] | None = None
    status: Literal['no_answer', 'connected'] | None = None


@router.get('/telephony/status')
def status():
    return telephony.configuration()


@router.get('/telephony/calls')
def calls(campaign_id: str | None = None, limit: int = Query(50, ge=1, le=200), db=Depends(get_db)):
    query = select(TelephonyCall)
    if campaign_id:
        query = query.where(TelephonyCall.campaign_id == campaign_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(TelephonyCall.created_at.desc()).limit(limit)).all()
    return {'items': [telephony.call_dict(row) for row in rows], 'total': total}


@router.post('/campaigns/{campaign_id}/notify', dependencies=[Depends(merchant_role)])
def notify(campaign_id: str, request: Request, data: NotifyRequest = NotifyRequest(), db=Depends(get_db)):
    from app.services import notifications
    row = notifications.queue_campaign_call(db, campaign_id, simulate=data.simulate)
    db.commit()
    return notifications.dispatch_call(db, row.id)


@router.post('/telephony/demo-offer', dependencies=[Depends(merchant_role)])
def demo_offer(data: NotifyRequest, request: Request, db=Depends(get_db)):
    def create():
        today = business_today()
        campaign = create_campaign(db, {'name': 'Kush comeback · ₹20 off ₹200', 'target_segment': 'At-Risk + Declining',
            'offer_amount': 20, 'minimum_bill': 200, 'budget': 200, 'max_customers': 10,
            'start_date': today.isoformat(), 'end_date': (today + timedelta(days=7)).isoformat(), 'language': 'en-IN', 'ab_test': False})
        # A one-person phone demo has no randomized control group.
        model = db.get(Campaign, campaign['id'])
        model.status = 'active'
        campaign = {**campaign, 'status': 'active'}
        emit(db, 'campaign.launched', 'Merchant started Kush comeback offer', 'One explicitly selected phone recipient; not a randomized experiment.',
             agent='comeback', data={'campaign_id': model.id})
        row = telephony.queue_campaign_call(db, campaign['id'], simulate=data.simulate)
        return {'campaign': campaign, 'call': telephony.call_dict(row)}
    result = execute_once(db, request.headers.get('Idempotency-Key'), request.url.path, data.model_dump(), create)
    db.commit()
    return {**result, 'call': telephony.dispatch_call(db, result['call']['id'])}


@router.post('/telephony/calls/{call_id}/simulate', dependencies=[Depends(merchant_role)])
def simulate(call_id: str, data: SimulateRequest, db=Depends(get_db)):
    if not data.digit and not data.status:
        raise HTTPException(422, 'Choose digit 1, digit 2, or a simulator call status')
    row = db.scalar(select(TelephonyCall).where(TelephonyCall.id == call_id).with_for_update())
    if not row:
        raise HTTPException(404, 'Call not found')
    result = telephony.apply_outcome(db, row, data.status or 'connected', digit=data.digit, source='simulation')
    db.commit()
    return result


@router.get('/telephony/audio/{call_id}')
def audio(call_id: str, token: str = '', db=Depends(get_db)):
    if not settings.telephony_webhook_secret or not hmac.compare_digest(token, telephony.capability(call_id, 'audio')):
        raise HTTPException(403, 'Invalid audio token')
    row = db.get(TelephonyCall, call_id)
    if not row or not row.audio_base64:
        raise HTTPException(404, 'Announcement audio not found')
    # Announcement URLs are capabilities, never exposed in dashboard responses.
    return Response(base64.b64decode(row.audio_base64), media_type='audio/wav', headers={'Cache-Control': 'private, max-age=300'})


async def twilio_call(request, db, call_id):
    if request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
        raise HTTPException(415, 'Expected provider form data')
    form = await request.form()
    # Build the ORIGINAL public URL from server configuration; do not trust Host
    # or proxy headers. Twilio signs that exact URL and all posted form fields.
    url = telephony.public_url(request.url.path)
    if request.url.query:
        url += '?' + request.url.query
    if not telephony.validate_twilio_signature(url, form, request.headers.get('X-Twilio-Signature', '')):
        raise HTTPException(403, 'Invalid Twilio signature')
    row = db.scalar(select(TelephonyCall).where(TelephonyCall.id == call_id).with_for_update())
    if not row or row.provider != 'twilio':
        raise HTTPException(404, 'Call not found')
    if form.get('AccountSid') != settings.twilio_account_sid or form.get('To') != row.phone:
        raise HTTPException(403, 'Call recipient or account mismatch')
    sid = form.get('CallSid', '')
    if not sid or (row.provider_attempt_id and sid != row.provider_attempt_id):
        raise HTTPException(409, 'Provider call does not match this offer')
    if not row.provider_attempt_id:
        if row.status != 'dispatching':
            raise HTTPException(409, 'This call was not submitted')
        row.provider_attempt_id = sid
    return row, form


@router.post('/telephony/webhooks/twilio-digits/{call_id}')
async def twilio_digits(call_id: str, request: Request, db=Depends(get_db)):
    row, form = await twilio_call(request, db, call_id)
    digit = form.get('Digits', '')
    if digit not in ('', '1', '2'):
        return Response('<Response><Say>Invalid choice. The offer was not accepted.</Say><Hangup/></Response>', media_type='application/xml')
    telephony.apply_outcome(db, row, 'completed', digit=digit or None)
    db.commit()
    message = 'Thank you. Your offer has been accepted. The discount will apply to your next eligible demo payment.' if row.accepted else 'Thank you. The offer has not been accepted.'
    return Response(f'<Response><Say>{message}</Say><Hangup/></Response>', media_type='application/xml')


@router.post('/telephony/webhooks/twilio-status/{call_id}')
async def twilio_status(call_id: str, request: Request, db=Depends(get_db)):
    row, form = await twilio_call(request, db, call_id)
    mapped = {'queued': 'submitted', 'initiated': 'submitted', 'ringing': 'ringing', 'in-progress': 'connected',
              'completed': 'completed', 'busy': 'busy', 'failed': 'failed', 'no-answer': 'no_answer', 'canceled': 'canceled'}
    outcome = mapped.get(form.get('CallStatus'))
    if outcome:
        telephony.apply_outcome(db, row, outcome)
    db.commit()
    return {'received': True}


@router.post('/telephony/webhooks/sarvam/{call_id}')
async def sarvam_outcome(call_id: str, request: Request, token: str = '', db=Depends(get_db)):
    if not settings.telephony_webhook_secret or not hmac.compare_digest(token, telephony.capability(call_id, 'sarvam')):
        raise HTTPException(403, 'Invalid callback token')
    body = await request.json()
    row = db.scalar(select(TelephonyCall).where(TelephonyCall.id == call_id).with_for_update())
    if not row or row.provider != 'sarvam':
        raise HTTPException(404, 'Call not found')
    if body.get('app_id') != settings.sarvam_voice_app_id or not body.get('attempt_id'):
        raise HTTPException(403, 'Agent or attempt mismatch')
    if row.provider_attempt_id and row.provider_attempt_id != body['attempt_id']:
        raise HTTPException(409, 'Provider call does not match this offer')
    if not row.provider_attempt_id:
        if row.status != 'dispatching':
            raise HTTPException(409, 'This call was not submitted')
        row.provider_attempt_id = body['attempt_id']
    # Extracted LLM variables and transcript are NEVER DTMF evidence.
    outcome = {'connected': 'completed', 'no_answer': 'no_answer', 'busy': 'busy', 'failed': 'failed'}.get(body.get('status'))
    if outcome:
        telephony.apply_outcome(db, row, outcome)
    db.commit()
    return {'received': True, 'call': telephony.call_dict(row)}
