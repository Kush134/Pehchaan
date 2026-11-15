import csv
import io
import json

import pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import func, select

from app.analytics.detail import weekly_cohorts
from app.core.clock import MERCHANT_TIMEZONE, business_today
from app.models import Campaign, NegotiationSession, Transaction
from app.services import requirement_parser, voice


class UnavailableProvider:
    async def chat(self, *args, **kwargs):
        return {'provider': 'demo', 'demo': True, 'text': '', 'error': 'Provider unavailable during test.'}


def test_customer_detail_uses_persisted_profile_and_purchase_evidence(client):
    profile = client.get('/api/v1/customers/PK-0001')
    assert profile.status_code == 200
    detail = profile.json()
    assert detail['customer']['customer_token'] == 'PK-0001'
    assert detail['rfm']['frequency'] == detail['customer']['total_transactions']
    assert detail['rfm']['monetary'] == detail['customer']['lifetime_spend']
    assert sum(day['amount'] for day in detail['spend_trend']) == pytest.approx(detail['customer']['lifetime_spend'],abs=.01)
    assert all(transaction['customer_token'] == 'PK-0001' for transaction in detail['transactions'])
    assert 'cannot identify purchases at other businesses' in detail['insights']['description']
    assert detail['synthetic'] is True
    assert 'phone' not in str(detail).lower() and 'upi' not in str(detail).lower()
    assert client.get('/api/v1/customers/not-a-known-token').status_code == 404


def test_new_customer_detail_does_not_claim_an_inactive_regular(client):
    customer = client.get('/api/v1/customers?segment=New%20Customers').json()['items'][0]
    detail = client.get('/api/v1/customers/' + customer['customer_token']).json()
    assert detail['insights']['cadence_status'] == 'insufficient_history'
    assert detail['insights']['inactivity_threshold_days'] is None


def test_cohorts_use_nonempty_weekly_denominators_and_leave_future_unmeasured(client):
    cohorts = client.get('/api/v1/dashboard/summary').json()['cohorts']
    assert cohorts and all(cohort['size'] > 0 for cohort in cohorts)
    assert all(cohort['period_days'] == 7 for cohort in cohorts)
    assert all(cohort['values'][0] == 100 for cohort in cohorts)
    assert any(value is None for cohort in cohorts for value in cohort['values'])
    assert all(value is None or 0 <= value <= 100 for cohort in cohorts for value in cohort['values'])


def test_cohort_week_boundaries_follow_india_business_dates():
    reference = datetime(2026, 11, 16, 1, tzinfo=MERCHANT_TIMEZONE)
    # A Monday-in-India purchase is still Sunday UTC and belongs to Monday's cohort.
    purchase = SimpleNamespace(customer_token='PK-0001', created_at=datetime(2026, 11, 15, 19, tzinfo=timezone.utc))
    future = SimpleNamespace(customer_token='PK-0002', created_at=reference + timedelta(hours=2))
    cohort = weekly_cohorts([purchase, future], reference)[0]
    assert cohort['start_date'] == '2026-11-16' and cohort['size'] == 1
    assert cohort['values'] == [100, None, None, None, None, None]


def test_structured_buyer_parsing_is_review_only_and_does_not_substitute_products(client, seeded, monkeypatch):
    class ParsedProvider:
        async def chat(self, messages, **kwargs):
            assert kwargs['structured'] is True
            assert 'seller' not in messages[1]['content']
            return {'provider': 'sarvam', 'demo': False, 'error': None, 'text': json.dumps({
                'items': [
                    {'product_id': 'rice', 'name': 'Basmati Rice', 'quantity': 100, 'unit': 'kg'},
                    {'product_id': 'rice', 'name': 'Organic Coffee', 'quantity': 5, 'unit': 'kg'},
                    {'product_id': 'oil', 'name': 'Sunflower Oil', 'quantity': 80, 'unit': 'litres'},
                ], 'budget': 40000, 'delivery_date': (business_today() + timedelta(days=5)).isoformat(), 'unmatched_items': [],
            })}
    monkeypatch.setattr(requirement_parser, 'SarvamProvider', ParsedProvider)
    before = seeded.scalar(select(func.count()).select_from(NegotiationSession))
    response = client.post('/api/v1/haggle/parse-requirement', json={'requirement': '100kg rice, 80 litres oil and 5kg coffee. Budget ₹40000. Friday.'})
    assert response.status_code == 200
    parsed = response.json()
    assert parsed['provider'] == 'sarvam' and not parsed['demo']
    assert parsed['review_required'] and parsed['status'] == 'partial'
    assert [line['product_id'] for line in parsed['items']] == ['rice', 'oil']
    assert parsed['unmatched_items'][0]['name'] == 'Organic Coffee'
    assert seeded.scalar(select(func.count()).select_from(NegotiationSession)) == before


def test_unavailable_parser_never_invents_a_default_basket(client, monkeypatch):
    monkeypatch.setattr(requirement_parser, 'SarvamProvider', UnavailableProvider)
    response = client.post('/api/v1/haggle/parse-requirement', json={'requirement': 'Office event groceries, budget ₹40,000, delivery Friday.'})
    parsed = response.json()
    assert parsed['items'] == [] and parsed['budget'] == 40000
    assert parsed['review_required'] and parsed['demo'] and parsed['error']
    assert parsed['status'] == 'unavailable' and 'items' in parsed['missing_fields']
    assert client.post('/api/v1/haggle/parse-requirement', json={'requirement': 'bad', 'budget': 9999}).status_code == 422


def test_local_parser_does_not_silently_turn_grams_into_kilograms(client, monkeypatch):
    monkeypatch.setattr(requirement_parser, 'SarvamProvider', UnavailableProvider)
    parsed = client.post('/api/v1/haggle/parse-requirement', json={'requirement': '500g rice and 2 litres oil, budget 500, tomorrow'}).json()
    assert [line['product_id'] for line in parsed['items']] == ['oil']
    assert any('whole kg' in line['reason'] for line in parsed['unmatched_items'])


def test_parser_rejects_unexpected_model_tool_or_policy_fields(client, monkeypatch):
    class MalformedProvider:
        async def chat(self, *args, **kwargs):
            return {'provider': 'sarvam', 'demo': False, 'error': None, 'text': '{"items":[],"budget":40000,"minimum_secret":35000,"tool":"payment"}'}
    monkeypatch.setattr(requirement_parser, 'SarvamProvider', MalformedProvider)
    parsed = client.post('/api/v1/haggle/parse-requirement', json={'requirement': '10kg rice, budget 40000, tomorrow'}).json()
    assert parsed['demo'] and parsed['provider'] == 'demo'
    assert 'minimum_secret' not in str(parsed) and '35000' not in str(parsed)
    assert parsed['items'][0]['quantity'] == 10


def test_voice_approval_receipt_survives_history_restore_without_duplicate_on_replay(client, monkeypatch):
    monkeypatch.setattr(voice, 'SarvamProvider', UnavailableProvider)
    proposal = client.post('/api/v1/voice/chat', json={'text': 'Create discount 15 minimum bill 250 campaign', 'language': 'mr-IN'}).json()
    request = {'session_id': proposal['session_id'], 'proposal_id': proposal['proposal']['id'], 'approved': True}
    receipt = client.post('/api/v1/voice/approve', json=request).json()
    restored = client.get('/api/v1/voice/history', params={'session_id': proposal['session_id']}).json()
    assert restored['language'] == 'mr-IN' and restored['status'] == 'active'
    assert restored['proposal']['status'] == 'approved'
    assert restored['messages'][-1]['text'] == receipt['response']
    assert restored['messages'][-1]['action_status'] == 'approved'
    assert 'provider' not in restored['messages'][-1]
    count = len(restored['messages'])
    client.post('/api/v1/voice/approve', json=request)
    assert len(client.get('/api/v1/voice/history', params={'session_id': proposal['session_id']}).json()['messages']) == count


def test_voice_rejection_is_persisted_without_creating_a_campaign(client, seeded, monkeypatch):
    monkeypatch.setattr(voice, 'SarvamProvider', UnavailableProvider)
    before = seeded.scalar(select(func.count()).select_from(Campaign))
    proposal = client.post('/api/v1/voice/chat', json={'text': 'Create discount 15 minimum bill 250 campaign', 'language': 'en-IN'}).json()
    receipt = client.post('/api/v1/voice/approve', json={'session_id': proposal['session_id'], 'proposal_id': proposal['proposal']['id'], 'approved': False}).json()
    history = client.get('/api/v1/voice/history', params={'session_id': proposal['session_id']}).json()
    assert receipt['status'] == 'rejected' and history['messages'][-1]['action_status'] == 'rejected'
    assert seeded.scalar(select(func.count()).select_from(Campaign)) == before


def test_transaction_template_uses_known_tokens_and_import_deduplicates_new_browser_keys(client):
    template = client.get('/api/v1/transactions/template')
    assert template.status_code == 200 and 'attachment' in template.headers['content-disposition']
    rows = list(csv.DictReader(io.StringIO(template.text)))
    assert len(rows) == 3 and all(row['customer_token'].startswith('PK-') for row in rows)
    before = client.get('/api/v1/transactions').json()['total']
    for key in ['first-browser-click', 'second-browser-click']:
        imported = client.post('/api/v1/transactions/import', files={'file': ('transactions.csv', template.content, 'text/csv')}, headers={'Idempotency-Key': key})
        assert imported.status_code == 200 and imported.json()['imported'] == 3
    assert client.get('/api/v1/transactions').json()['total'] == before + 3
    assert client.get('/api/v1/transactions/template', headers={'X-Demo-Role': 'buyer'}).status_code == 403


def test_transaction_export_marks_synthetic_data_and_escapes_spreadsheet_formulas(client, seeded):
    transaction = seeded.scalar(select(Transaction).limit(1))
    transaction.category = '=HYPERLINK("https://example.invalid")'
    seeded.commit()
    response = client.get('/api/v1/transactions/export')
    assert response.status_code == 200 and response.headers['x-data-source'] == 'synthetic'
    rows = list(csv.DictReader(io.StringIO(response.text)))
    row = next(row for row in rows if row['id'] == transaction.id)
    assert row['category'].startswith("'=") and row['simulated'] == 'true'
    assert client.get('/api/v1/transactions/export', headers={'X-Demo-Role': 'buyer'}).status_code == 403


def test_explicit_calendar_quantities_and_budget_override_model_mistakes(client, monkeypatch):
    from datetime import date
    monkeypatch.setattr(requirement_parser, 'business_today', lambda: date(2026, 11, 14))
    class MistakenProvider:
        async def chat(self, *args, **kwargs):
            return {'provider': 'sarvam', 'demo': False, 'error': None, 'text': json.dumps({
                'items': [{'product_id': 'rice', 'name': 'Rice', 'quantity': 9, 'unit': 'kg'}],
                'budget': 40, 'delivery_date': '2026-11-17',
                'unmatched_items': [{'name': 'Wheat Flour', 'reason': 'Unsupported product'}],
            })}
    monkeypatch.setattr(requirement_parser, 'SarvamProvider', MistakenProvider)
    parsed = client.post('/api/v1/haggle/parse-requirement', json={'requirement': '100kg rice and 80kg wheat flour, budget40k, Friday'}).json()
    assert parsed['provider'] == 'sarvam' and parsed['status'] == 'parsed'
    assert parsed['delivery_date'] == '2026-11-20' and parsed['budget'] == 40000
    assert {item['product_id']: item['quantity'] for item in parsed['items']} == {'rice': 100, 'atta': 80}
    assert parsed['unmatched_items'] == []


@pytest.mark.parametrize('requirement', ['0.5kg rice with budget1000', '0kg rice with budget1000', '10001kg rice with budget1000'])
def test_explicit_invalid_quantity_cannot_be_replaced_with_model_invention(client, monkeypatch, requirement):
    class MistakenProvider:
        async def chat(self, *args, **kwargs):
            return {'provider': 'sarvam', 'demo': False, 'error': None, 'text': json.dumps({
                'items': [{'product_id': 'rice', 'name': 'Rice', 'quantity': 100, 'unit': 'kg'}],
                'budget': 1000, 'delivery_date': None, 'unmatched_items': [],
            })}
    monkeypatch.setattr(requirement_parser, 'SarvamProvider', MistakenProvider)
    parsed = client.post('/api/v1/haggle/parse-requirement', json={'requirement': requirement}).json()
    assert parsed['items'] == [] and parsed['unmatched_items']
    assert 'items' in parsed['missing_fields']


def test_local_budget_parser_distinguishes_unit_price_and_budget_scale():
    from datetime import date
    assert requirement_parser.local_fields('100kg rice at ₹85 per kg', date(2026, 11, 14)).budget is None
    assert requirement_parser.local_fields('budget1lakh', date(2026, 11, 14)).budget == 100000
    assert requirement_parser.local_fields('budget ₹40 हजार', date(2026, 11, 14)).budget == 40000
