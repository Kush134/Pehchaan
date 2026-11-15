import base64
import hashlib
import hmac

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import TelephonyCall, CampaignAssignment
from app.services import telephony


def configure(monkeypatch):
    for key, value in {'telephony_enabled': True, 'telephony_provider': 'twilio',
        'telephony_public_base_url': 'https://merchant.example', 'telephony_webhook_secret': 's' * 64,
        'twilio_account_sid': 'ACtest', 'twilio_auth_token': 'test-auth',
        'twilio_api_key_sid': '', 'twilio_api_key_secret': '', 'twilio_from_number': '+18005550123',
        'sarvam_api_key': 'test-speech-key'}.items():
        monkeypatch.setattr(settings, key, value)


def offer(client, simulate=True):
    response = client.post('/api/v1/telephony/demo-offer', json={'simulate': simulate})
    assert response.status_code == 200, response.text
    return response.json()


def sign(path, body):
    url = 'https://merchant.example' + path
    content = url + ''.join(key + body[key] for key in sorted(body))
    signature = base64.b64encode(hmac.new(b'test-auth', content.encode(), hashlib.sha1).digest()).decode()
    return {'X-Twilio-Signature': signature}


def test_simulated_offer_acceptance_is_persistent_and_explicit(client, seeded):
    data = offer(client)
    call = data['call']
    assert call['provider'] == 'simulation' and not call['accepted']
    assert 'phone' not in call and 'audio_base64' not in call
    assert call['offer_amount'] == 20 and call['minimum_bill'] == 200
    result = client.post(f'/api/v1/telephony/calls/{call["id"]}/simulate', json={'digit': '1'})
    assert result.json()['accepted'] is True
    assert result.json()['acceptance_source'] == 'simulation'
    # Duplicate provider events cannot undo the customer's accepted decision.
    repeat = client.post(f'/api/v1/telephony/calls/{call["id"]}/simulate', json={'digit': '2'})
    assert repeat.json()['status'] == 'accepted'
    assert client.get('/api/v1/telephony/calls').json()['items'][0]['accepted']
    assignment = seeded.scalar(select(CampaignAssignment).where(CampaignAssignment.campaign_id == call['campaign_id']))
    assert assignment.variant == 'Phone'


def test_missing_configuration_blocks_live_call_and_cannot_fake_acceptance(client, monkeypatch):
    monkeypatch.setattr(settings, 'telephony_enabled', False)
    monkeypatch.setattr(settings, 'twilio_account_sid', '')
    monkeypatch.setattr(telephony.httpx, 'post', lambda *args, **kwargs: pytest.fail('No outbound request should be made'))
    data = offer(client, simulate=False)
    assert data['call']['status'] == 'blocked'
    assert 'TWILIO_ACCOUNT_SID' in data['call']['error']
    response = client.post(f'/api/v1/telephony/calls/{data["call"]["id"]}/simulate', json={'digit': '1'})
    assert response.status_code == 409
    assert 'TWILIO_ACCOUNT_SID' in client.get('/api/v1/telephony/status').json()['missing']


def test_live_twilio_gather_signed_acceptance_and_replay(client, seeded, monkeypatch):
    configure(monkeypatch)
    requests = []
    monkeypatch.setattr(telephony, 'synthesize_announcement', lambda row: base64.b64encode(b'RIFF-test-audio').decode())
    def outbound(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(201, json={'sid': 'CAtest'}, request=httpx.Request('POST', url))
    monkeypatch.setattr(telephony.httpx, 'post', outbound)
    data = offer(client, simulate=False)
    call = data['call']
    assert call['status'] == 'submitted'
    assert len(requests) == 1
    assert requests[0][1]['auth'] == ('ACtest', 'test-auth')
    sent = requests[0][1]['data']
    assert sent['To'] == settings.telephony_demo_phone
    assert '<Gather input="dtmf" numDigits="1"' in sent['Twiml']
    assert '<Play>https://merchant.example/api/v1/telephony/audio/' in sent['Twiml']
    again = client.post(f'/api/v1/campaigns/{call["campaign_id"]}/notify', json={})
    assert again.status_code == 200 and len(requests) == 1
    path = f'/api/v1/telephony/webhooks/twilio-digits/{call["id"]}'
    body = {'AccountSid': 'ACtest', 'CallSid': 'CAtest', 'To': settings.telephony_demo_phone, 'Digits': '1'}
    assert client.post(path, data=body).status_code == 403
    wrong = {**body, 'CallSid': 'CAwrong'}
    assert client.post(path, data=wrong, headers=sign(path, wrong)).status_code == 409
    # A completed status can arrive before the digits request over the network.
    status_path = f'/api/v1/telephony/webhooks/twilio-status/{call["id"]}'
    completed = {k: v for k, v in body.items() if k != 'Digits'} | {'CallStatus': 'completed'}
    assert client.post(status_path, data=completed, headers=sign(status_path, completed)).status_code == 200
    assert client.post(path, data=body, headers=sign(path, body)).status_code == 200
    seeded.expire_all()
    row = seeded.get(TelephonyCall, call['id'])
    assert row.accepted and row.acceptance_source == 'live'
    client.post(status_path, data=completed, headers=sign(status_path, completed))
    seeded.expire_all()
    assert seeded.get(TelephonyCall, call['id']).status == 'accepted'


def test_timeout_does_not_redial(client, monkeypatch):
    configure(monkeypatch)
    attempts = []
    monkeypatch.setattr(telephony, 'synthesize_announcement', lambda row: base64.b64encode(b'RIFF-test').decode())
    def timeout(*args, **kwargs):
        attempts.append(True)
        raise httpx.ReadTimeout('provider response lost')
    monkeypatch.setattr(telephony.httpx, 'post', timeout)
    data = offer(client, simulate=False)
    assert data['call']['status'] == 'unknown'
    client.post(f'/api/v1/campaigns/{data["campaign"]["id"]}/notify', json={})
    assert len(attempts) == 1


def test_demo_offer_idempotency_and_no_answer(client):
    headers = {'Idempotency-Key': 'same-button-click'}
    first = client.post('/api/v1/telephony/demo-offer', json={'simulate': True}, headers=headers).json()
    second = client.post('/api/v1/telephony/demo-offer', json={'simulate': True}, headers=headers).json()
    assert first['call']['id'] == second['call']['id']
    call_id = first['call']['id']
    result = client.post(f'/api/v1/telephony/calls/{call_id}/simulate', json={'status': 'no_answer'}).json()
    assert result['status'] == 'no_answer' and not result['accepted']


def test_native_sarvam_uses_workspace_key_and_never_guesses_keypad_acceptance(client, monkeypatch):
    configure(monkeypatch)
    for key, value in {'telephony_provider': 'sarvam', 'sarvam_voice_api_key': 'workspace-key',
        'sarvam_voice_org_id': 'org', 'sarvam_voice_workspace_id': 'workspace',
        'sarvam_voice_app_id': 'comeback-agent', 'sarvam_voice_connection_id': 'connection',
        'sarvam_voice_agent_phone': '+18005550123'}.items():
        monkeypatch.setattr(settings, key, value)
    requests = []
    def outbound(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(200, json={'attempt_id': 'attempt-1'}, request=httpx.Request('POST', url))
    monkeypatch.setattr(telephony.httpx, 'post', outbound)
    data = offer(client, simulate=False)
    assert data['call']['status'] == 'submitted'
    assert requests[0][0] == 'https://apps.sarvam.ai/api/outbounds/v1/orgs/org/workspaces/workspace/outbounds'
    assert requests[0][1]['headers']['X-API-Key'] == 'workspace-key'
    call_id = data['call']['id']
    path = f'/api/v1/telephony/webhooks/sarvam/{call_id}?token={telephony.capability(call_id, "sarvam")}'
    body = {'attempt_id': 'attempt-1', 'app_id': 'comeback-agent', 'status': 'connected',
            'final_agent_variables': {'accepted': True, 'digit': '1'}}
    response = client.post(path, json=body)
    assert response.status_code == 200
    assert response.json()['call']['status'] == 'completed'
    assert response.json()['call']['accepted'] is False


def test_phone_offer_reserves_campaign_budget(client, seeded, monkeypatch):
    first = offer(client)
    from app.models import Campaign
    campaign = seeded.get(Campaign, first['campaign']['id'])
    campaign.budget = 20
    seeded.commit()
    monkeypatch.setattr(settings, 'telephony_demo_customer_token', 'PK-0037')
    with pytest.raises(Exception) as error:
        telephony.queue_campaign_call(seeded, campaign.id, simulate=True)
    assert getattr(error.value, 'status_code', None) == 422
    assert 'budget' in str(error.value.detail)


def test_api_key_authenticates_calls_without_changing_webhook_signing(client, seeded, monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(settings, 'twilio_api_key_sid', 'SKtest')
    monkeypatch.setattr(settings, 'twilio_api_key_secret', 'api-key-secret')
    monkeypatch.setattr(telephony, 'synthesize_announcement', lambda row: base64.b64encode(b'RIFF-test').decode())
    requests = []
    def outbound(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(201, json={'sid': 'CAkeycall'}, request=httpx.Request('POST', url))
    monkeypatch.setattr(telephony.httpx, 'post', outbound)
    data = offer(client, simulate=False)
    assert data['call']['status'] == 'submitted'
    assert '/Accounts/ACtest/Calls.json' in requests[0][0]
    assert requests[0][1]['auth'] == ('SKtest', 'api-key-secret')
    path = f'/api/v1/telephony/webhooks/twilio-digits/{data["call"]["id"]}'
    body = {'AccountSid': 'ACtest', 'CallSid': 'CAkeycall', 'To': settings.telephony_demo_phone, 'Digits': '1'}
    # The webhook must still use the account Auth Token, not the API key secret.
    content = 'https://merchant.example' + path + ''.join(k + body[k] for k in sorted(body))
    wrong_signature = base64.b64encode(hmac.new(b'api-key-secret', content.encode(), hashlib.sha1).digest()).decode()
    assert client.post(path, data=body, headers={'X-Twilio-Signature': wrong_signature}).status_code == 403
    assert client.post(path, data=body, headers=sign(path, body)).status_code == 200
    assert seeded.get(TelephonyCall, data['call']['id']).accepted


@pytest.mark.parametrize('present,missing', [('twilio_api_key_sid', 'TWILIO_API_KEY_SECRET'), ('twilio_api_key_secret', 'TWILIO_API_KEY_SID')])
def test_partial_api_key_configuration_blocks_dial_instead_of_falling_back(client, monkeypatch, present, missing):
    configure(monkeypatch)
    monkeypatch.setattr(settings, present, 'test-value')
    monkeypatch.setattr(telephony.httpx, 'post', lambda *args, **kwargs: pytest.fail('Incomplete API key must never dial'))
    assert missing in telephony.configuration()['missing']
    data = offer(client, simulate=False)
    assert data['call']['status'] == 'blocked'
    assert missing in data['call']['error']


@pytest.mark.parametrize('failure', ['timeout', 'provider_error', 'invalid_audio'])
def test_announcement_failure_is_definite_and_never_submits_to_twilio(client, seeded, monkeypatch, failure):
    configure(monkeypatch)
    def unavailable(row):
        if failure == 'timeout':
            raise httpx.ReadTimeout('Sarvam response unavailable')
        if failure == 'provider_error':
            request = httpx.Request('POST', 'https://speech.example')
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError('Speech unavailable', request=request, response=response)
        raise ValueError('No audio')
    monkeypatch.setattr(telephony, 'synthesize_announcement', unavailable)
    monkeypatch.setattr(telephony.httpx, 'post', lambda *args, **kwargs: pytest.fail('Twilio must not be called before audio is ready'))
    data = offer(client, simulate=False)
    call = data['call']
    assert call['status'] == 'failed'
    assert call['error'] == 'Sarvam announcement unavailable; no phone call was placed.'
    row = seeded.get(TelephonyCall, call['id'])
    assert row.provider_attempt_id is None and row.audio_base64 is None
    # A retry of this request returns its definite failure, without an implicit redial.
    retry = client.post(f'/api/v1/campaigns/{call["campaign_id"]}/notify', json={})
    assert retry.status_code == 200 and retry.json()['status'] == 'failed'
