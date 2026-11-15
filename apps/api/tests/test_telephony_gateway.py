"""The development tunnel cannot expose merchant or call-trigger APIs."""
import pytest
from fastapi.testclient import TestClient
from app.telephony_gateway import app
from app.database.session import get_db


@pytest.fixture
def gateway(db):
    def override():
        yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.parametrize('method,path', [
    ('GET', '/api/v1/telephony/status'),
    ('GET', '/api/v1/telephony/calls'),
    ('POST', '/api/v1/telephony/demo-offer'),
    ('POST', '/api/v1/telephony/calls/test/simulate'),
    ('GET', '/api/v1/campaigns'),
    ('POST', '/api/v1/campaigns/test/notify'),
    ('POST', '/api/v1/checkout/pay'),
    ('GET', '/docs'),
    ('GET', '/redoc'),
    ('GET', '/openapi.json'),
])
def test_merchant_and_documentation_routes_not_public(gateway, method, path):
    assert gateway.request(method, path, content=b'').status_code == 404


def test_callback_gateway_preserves_provider_authentication(gateway):
    for provider in ('twilio-digits', 'twilio-status'):
        response = gateway.post(f'/api/v1/telephony/webhooks/{provider}/test', data={'Digits': '1'})
        assert response.status_code == 403
    assert gateway.post('/api/v1/telephony/webhooks/sarvam/test', json={}).status_code == 403
    assert gateway.get('/api/v1/telephony/audio/test?token=invalid').status_code == 403
    assert gateway.get('/health').json() == {'status': 'ok', 'service': 'telephony-callbacks'}


def test_oversized_callback_is_rejected_before_parsing(gateway):
    assert gateway.post('/api/v1/telephony/webhooks/twilio-status/test', content=b'x'*65537).status_code == 413
