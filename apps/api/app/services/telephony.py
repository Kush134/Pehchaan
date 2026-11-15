"""Durable, allowlisted campaign calls. No automatic retries after an uncertain dial.

Twilio handles real DTMF; Sarvam supplies the announcement audio. Native Sarvam
Voice Agents instant-outbound is also supported, with call outcomes only.
"""
import base64
import hashlib
import hmac
import re
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit
from xml.etree.ElementTree import Element, SubElement, tostring

import httpx
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.clock import business_today
from app.core.config import settings
from app.models import Campaign, CampaignAssignment, CampaignVariant, CustomerToken, TelephonyCall, Redemption
from app.services.events import emit

TERMINAL = {'accepted', 'declined', 'completed', 'no_answer', 'busy', 'failed', 'canceled'}
RANK = {'queued': 0, 'dispatching': 1, 'submitted': 2, 'ringing': 3, 'connected': 4}


def masked_phone(phone):
    return phone[:3] + '••••••' + phone[-4:] if len(phone) > 7 else 'Not configured'


def configuration():
    common = ['telephony_public_base_url', 'telephony_webhook_secret']
    if settings.telephony_provider == 'twilio':
        required = common + ['twilio_account_sid', 'twilio_auth_token', 'twilio_from_number', 'sarvam_api_key']
    elif settings.telephony_provider == 'sarvam':
        required = common + ['sarvam_voice_api_key', 'sarvam_voice_org_id', 'sarvam_voice_workspace_id',
                             'sarvam_voice_app_id', 'sarvam_voice_connection_id', 'sarvam_voice_agent_phone']
    else:
        required = common + ['telephony_provider']
    missing = [name.upper() for name in required if not getattr(settings, name, '')]
    if settings.telephony_provider == 'twilio' and bool(settings.twilio_api_key_sid) != bool(settings.twilio_api_key_secret):
        missing.append('TWILIO_API_KEY_SECRET' if settings.twilio_api_key_sid else 'TWILIO_API_KEY_SID')
    if settings.telephony_provider not in ('twilio', 'sarvam'):
        missing.append('TELEPHONY_PROVIDER (twilio or sarvam)')
    parsed = urlsplit(settings.telephony_public_base_url)
    if settings.telephony_public_base_url and (parsed.scheme != 'https' or not parsed.hostname or parsed.query or parsed.fragment or parsed.username):
        missing.append('TELEPHONY_PUBLIC_BASE_URL (public HTTPS URL without query)')
    if settings.telephony_webhook_secret and len(settings.telephony_webhook_secret) < 32:
        missing.append('TELEPHONY_WEBHOOK_SECRET (at least 32 characters)')
    if not re.fullmatch(r'\+[1-9]\d{7,14}', settings.telephony_demo_phone):
        missing.append('TELEPHONY_DEMO_PHONE (E.164)')
    if not settings.telephony_enabled:
        missing.append('TELEPHONY_ENABLED')
    return {'configured': not missing, 'enabled': settings.telephony_enabled,
            'provider': settings.telephony_provider, 'missing': missing,
            'customer_name': settings.telephony_demo_customer_name,
            'customer_token': settings.telephony_demo_customer_token,
            'masked_phone': masked_phone(settings.telephony_demo_phone),
            'simulation_available': True, 'supports_dtmf': settings.telephony_provider == 'twilio',
            'note': 'Twilio carries the phone call and keypad input; Sarvam generates the voice.' if settings.telephony_provider == 'twilio' else
                    'Native Sarvam outbound reports call outcomes. General keypad DTMF is not available; choose Twilio for press 1.'}


def call_dict(row):
    return {name: getattr(row, name) for name in ('id', 'campaign_id', 'customer_token', 'customer_name',
            'status', 'provider', 'offer_amount', 'minimum_bill', 'accepted', 'acceptance_source', 'redeemed',
            'checkout_id', 'error', 'script')} | {'masked_phone': masked_phone(row.phone),
            'created_at': row.created_at.isoformat(), 'updated_at': row.updated_at.isoformat(),
            'accepted_at': row.accepted_at.isoformat() if row.accepted_at else None}


def queue_campaign_call(db, campaign_id, simulate=False):
    campaign = db.scalar(select(Campaign).where(Campaign.id == campaign_id).with_for_update())
    if not campaign:
        raise HTTPException(404, 'Campaign not found')
    if campaign.status != 'active':
        raise HTTPException(409, 'Start the campaign before sending a notification')
    if not campaign.start_date <= business_today().isoformat() <= campaign.end_date:
        raise HTTPException(422, 'Campaign is outside its active date range')
    token = settings.telephony_demo_customer_token
    if not db.get(CustomerToken, token):
        raise HTTPException(422, 'The configured demo customer does not exist. Seed the database first.')
    existing = db.scalar(select(TelephonyCall).where(TelephonyCall.campaign_id == campaign_id, TelephonyCall.customer_token == token))
    if existing:
        if simulate and existing.provider != 'simulation':
            raise HTTPException(409, 'Create a new simulator offer; a real call cannot be changed into a simulated acceptance.')
        return existing
    assignment = db.scalar(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign_id, CampaignAssignment.customer_token == token))
    if assignment and (assignment.redeemed or db.scalar(select(Redemption.id).where(Redemption.assignment_id == assignment.id))):
        raise HTTPException(409, 'This customer already redeemed the campaign. Create a new offer.')
    variants = {v.name: v.offer_amount for v in db.scalars(select(CampaignVariant).where(CampaignVariant.campaign_id == campaign_id)).all()}
    assignments = db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign_id)).all()
    reserved = sum(variants.get(a.variant, campaign.offer_amount) for a in assignments if a.variant != 'Control' and a.customer_token != token)
    if reserved + campaign.offer_amount > campaign.budget + .001:
        raise HTTPException(422, 'The campaign budget cannot cover this phone offer. Increase the budget or create a new offer.')
    # An explicitly contacted customer is not part of a randomized holdout.
    if assignment:
        assignment.variant = 'Phone'
    else:
        db.add(CampaignAssignment(campaign_id=campaign_id, customer_token=token, variant='Phone'))
    conf = configuration()
    script = (f'Hi {settings.telephony_demo_customer_name}! You have not visited Sharma Kirana Store recently. '
              f'We have an offer: {campaign.offer_amount:g} rupees off an order of {campaign.minimum_bill:g} rupees or more. '
              'To accept this offer, press 1. To decline, press 2.')
    row = TelephonyCall(campaign_id=campaign_id, customer_token=token, customer_name=settings.telephony_demo_customer_name,
        phone=settings.telephony_demo_phone, provider='simulation' if simulate else settings.telephony_provider,
        status='ringing' if simulate else ('queued' if conf['configured'] else 'blocked'),
        offer_amount=campaign.offer_amount, minimum_bill=campaign.minimum_bill, script=script,
        error=None if simulate or conf['configured'] else 'Live calling requires: ' + ', '.join(conf['missing']))
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return db.scalar(select(TelephonyCall).where(TelephonyCall.campaign_id == campaign_id, TelephonyCall.customer_token == token))
    emit(db, 'telephony.' + row.status, 'Simulator call ready' if simulate else 'Customer call ' + row.status,
         'Only the configured demo recipient is contacted.' if row.status == 'queued' else (row.error or 'Explicit local simulation; no phone call placed.'),
         agent='comeback', data={'call_id': row.id, 'campaign_id': campaign_id, 'provider': row.provider})
    return row


def capability(call_id, purpose):
    return hmac.new(settings.telephony_webhook_secret.encode(), f'{purpose}:{call_id}'.encode(), hashlib.sha256).hexdigest()


def public_url(path):
    return settings.telephony_public_base_url.rstrip('/') + path


def callback_url(row, purpose):
    return public_url(f'/api/v1/telephony/webhooks/{purpose}/{row.id}')


def audio_url(row):
    return public_url(f'/api/v1/telephony/audio/{row.id}?token={capability(row.id, "audio")}')


def twiml(row):
    root = Element('Response')
    gather = SubElement(root, 'Gather', input='dtmf', numDigits='1', timeout='12',
                        action=callback_url(row, 'twilio-digits'), method='POST', actionOnEmptyResult='true')
    SubElement(gather, 'Play').text = audio_url(row)
    SubElement(root, 'Hangup')
    return tostring(root, encoding='unicode')


def synthesize_announcement(row):
    # This is the same configured Sarvam SDK contract as Soundbox synthesis.
    # Calling the synchronous SDK here also works from synchronous API workers.
    from sarvamai import SarvamAI
    client = SarvamAI(api_subscription_key=settings.sarvam_api_key, timeout=min(settings.api_timeout_seconds, 25))
    result = client.text_to_speech.convert(text=row.script, language_code='en-IN', model=settings.sarvam_tts_model,
                                          output_audio_codec='wav', speech_sample_rate=22050)
    audio = result.audios[0] if result.audios else None
    if not audio or not base64.b64decode(audio, validate=True):
        raise ValueError('Sarvam returned no announcement audio')
    return audio


def record_dispatch_error(db, row, status, message):
    # A provider callback may arrive while the HTTP client is still waiting.
    # Never replace verified customer input or connected progress with a later
    # transport error from that original submission request.
    db.refresh(row)
    if row.status not in TERMINAL and RANK.get(row.status, -1) < RANK['ringing']:
        row.status = status
        row.error = message


def twilio_rest_auth():
    # REST API keys and the account webhook signing token have different jobs.
    # Do not silently fall back when a partially configured API key is present.
    if bool(settings.twilio_api_key_sid) != bool(settings.twilio_api_key_secret):
        raise ValueError('Configure both TWILIO_API_KEY_SID and TWILIO_API_KEY_SECRET')
    if settings.twilio_api_key_sid:
        return settings.twilio_api_key_sid, settings.twilio_api_key_secret
    return settings.twilio_account_sid, settings.twilio_auth_token


def dispatch_call(db, call_id):
    row = db.get(TelephonyCall, call_id)
    if not row:
        raise HTTPException(404, 'Call not found')
    if row.provider == 'simulation' or row.status not in ('queued', 'blocked'):
        return call_dict(row)
    conf = configuration()
    if not conf['configured']:
        row.status = 'blocked'; row.error = 'Live calling requires: ' + ', '.join(conf['missing'])
        db.commit()
        return call_dict(row)
    if row.phone != settings.telephony_demo_phone or row.provider != settings.telephony_provider:
        raise HTTPException(409, 'The configured recipient or provider changed; create a new offer.')
    # Atomic claim is committed BEFORE any network request. A repeated click or
    # timeout can never silently redial an already submitted/uncertain call.
    claimed = db.execute(update(TelephonyCall).where(TelephonyCall.id == call_id, TelephonyCall.status.in_(['queued', 'blocked']))
                         .values(status='dispatching', error=None))
    db.commit(); db.refresh(row)
    if not claimed.rowcount:
        return call_dict(row)
    # Only an error after the outbound POST starts can leave dialing uncertain.
    # In particular, a Sarvam speech timeout happens before Twilio sees a call.
    submission_started = False
    announcement_prepared = False
    try:
        if row.provider == 'twilio':
            row.audio_base64 = synthesize_announcement(row)
            announcement_prepared = True
            db.commit()
            url = f'https://api.twilio.com/2010-04-01/Accounts/{quote(settings.twilio_account_sid, safe="")}/Calls.json'
            payload = {'To': row.phone, 'From': settings.twilio_from_number, 'Twiml': twiml(row),
                       'StatusCallback': callback_url(row, 'twilio-status'), 'StatusCallbackMethod': 'POST',
                       'StatusCallbackEvent': ['initiated', 'ringing', 'answered', 'completed'], 'Timeout': '25', 'TimeLimit': '90'}
            rest_auth = twilio_rest_auth()
            submission_started = True
            response = httpx.post(url, data=payload, auth=rest_auth, timeout=25)
            response.raise_for_status()
            attempt = response.json().get('sid')
        else:
            url = ('https://apps.sarvam.ai/api/outbounds/v1/orgs/' + quote(settings.sarvam_voice_org_id, safe='') +
                   '/workspaces/' + quote(settings.sarvam_voice_workspace_id, safe='') + '/outbounds')
            payload = {'app_config': {'app_id': settings.sarvam_voice_app_id, 'app_version': settings.sarvam_voice_app_version,
                'connection_config': {'connection_id': settings.sarvam_voice_connection_id, 'agent_phone_number': settings.sarvam_voice_agent_phone},
                'agent_variables': {'customer_name': row.customer_name, 'offer_amount': row.offer_amount, 'minimum_bill': row.minimum_bill, 'call_id': row.id},
                'app_overrides': {'initial_bot_message': row.script, 'initial_language_name': 'English'}},
                'user_config': {'user_phone_number': row.phone},
                'webhook_config': {'url': callback_url(row, 'sarvam') + '?token=' + capability(row.id, 'sarvam'),
                                   'metadata': {'call_id': row.id}}}
            submission_started = True
            response = httpx.post(url, json=payload, headers={'X-API-Key': settings.sarvam_voice_api_key}, timeout=25)
            response.raise_for_status()
            attempt = response.json().get('attempt_id')
        if not isinstance(attempt, str) or not attempt:
            raise ValueError('Provider returned no call identifier')
        db.refresh(row)
        if row.provider_attempt_id and row.provider_attempt_id != attempt:
            raise ValueError('Call identifier mismatch')
        row.provider_attempt_id = attempt
        if row.status == 'dispatching': row.status = 'submitted'
        emit(db, 'telephony.submitted', 'Call submitted to provider', 'Waiting for the recipient to answer.', agent='comeback', data={'call_id': row.id})
    except Exception as exc:
        if not submission_started:
            message = ('Sarvam announcement unavailable; no phone call was placed.'
                       if row.provider == 'twilio' and not announcement_prepared
                       else 'Call preparation failed; no phone call was placed.')
            record_dispatch_error(db, row, 'failed', message)
        elif isinstance(exc, httpx.HTTPStatusError):
            # Provider 4xx is a definite rejection. A 5xx might have accepted a call.
            record_dispatch_error(db, row, 'failed' if exc.response.status_code < 500 else 'unknown',
                f'Calling provider returned HTTP {exc.response.status_code}. Check provider credentials and call logs.')
        elif isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
            record_dispatch_error(db, row, 'unknown', 'Provider response was not received. Check provider call logs before trying a new campaign; no automatic redial.')
        else:
            record_dispatch_error(db, row, 'unknown',
                'Call submission could not be confirmed. Check provider call logs; no automatic redial.')
    db.commit()
    return call_dict(row)


def apply_outcome(db, row, status, digit=None, source='live'):
    if source == 'simulation' and row.provider != 'simulation':
        raise HTTPException(409, 'Real calls cannot be accepted through the simulator')
    # The provider's completed callback can overtake the Gather response. A
    # cryptographically verified digit may finalize completed -> accepted;
    # accepted/declined and genuine failed/no-answer outcomes never reverse.
    if row.status in TERMINAL and not (digit in ('1', '2') and row.status == 'completed'):
        return call_dict(row)
    if digit == '1':
        row.accepted = True; row.accepted_at = datetime.now(timezone.utc)
        row.acceptance_source = source; row.status = 'accepted'
    elif digit == '2':
        row.status = 'declined'
    elif status in TERMINAL or RANK.get(status, -1) > RANK.get(row.status, -1):
        row.status = status
    else:
        return call_dict(row)
    emit(db, 'telephony.' + row.status, f'{row.customer_name}: {row.status.replace("_", " ")}',
         ('Simulated ' if source == 'simulation' else '') + ('Customer pressed ' + digit if digit else 'Call status updated'),
         agent='comeback', data={'call_id': row.id, 'campaign_id': row.campaign_id, 'accepted': row.accepted, 'source': source})
    db.flush()
    return call_dict(row)


def validate_twilio_signature(url, form, signature):
    if not settings.twilio_auth_token or not signature:
        return False
    content = url
    for key in sorted(form.keys()):
        values = sorted(set(form.getlist(key))) if hasattr(form, 'getlist') else [str(form[key])]
        for value in values:
            content += key + value
    expected = base64.b64encode(hmac.new(settings.twilio_auth_token.encode(), content.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(signature, expected)
