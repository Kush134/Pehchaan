"""Acceptance, pricing and one-use redemption across durable retail checkout."""
from datetime import timedelta
from sqlalchemy import select, func
from app.models import Campaign, CustomerToken, Merchant, TelephonyCall, Transaction, Redemption
from app.core.clock import business_today


def accepted_offer(db, **overrides):
    today = business_today()
    if not db.get(Merchant, 'sharma-kirana'):
        db.add(Merchant(id='sharma-kirana', name='Kirana', location='Pune'))
        db.flush()
    if not db.get(CustomerToken, 'PK-0036'):
        db.add(CustomerToken(customer_token='PK-0036', merchant_id='sharma-kirana'))
        db.flush()
    c = Campaign(merchant_id='sharma-kirana', name='Phone offer', target_segment='All', offer_amount=20,
                 minimum_bill=200, budget=100, max_customers=2, language='en-IN', ab_test=False,
                 start_date=today.isoformat(), end_date=(today+timedelta(days=7)).isoformat(), status='active')
    db.add(c); db.flush()
    call = TelephonyCall(campaign_id=c.id, customer_token='PK-0036', customer_name='Kush', phone='+15005550006',
                         status='accepted', provider='simulation', accepted=True, offer_amount=20,
                         minimum_bill=200, script='test', acceptance_source='simulation', **overrides)
    db.add(call); db.commit()
    return call


def test_accepted_250_bill_becomes_230_once(client, seeded):
    call = accepted_offer(seeded)
    before = seeded.scalar(select(func.count(Transaction.id)))
    q = client.post('/api/v1/checkout/quote', json={'customer_token': call.customer_token, 'bill_amount': 250}).json()
    assert q['discount'] == 20 and q['payable_amount'] == 230 and q['acceptance_source'] == 'simulation'
    paid = client.post('/api/v1/checkout/pay', json={'quote_id': q['id']}, headers={'Idempotency-Key': 'retail-pay'})
    assert paid.status_code == 200 and paid.json()['status'] == 'paid'
    replay = client.post('/api/v1/checkout/pay', json={'quote_id': q['id']}, headers={'Idempotency-Key': 'retail-pay'})
    assert replay.json()['transaction_id'] == paid.json()['transaction_id']
    # Even a new browser idempotency key cannot pay the same quote twice.
    assert client.post('/api/v1/checkout/pay', json={'quote_id': q['id']}).json()['transaction_id'] == paid.json()['transaction_id']
    assert seeded.scalar(select(func.count(Transaction.id))) == before+1
    assert seeded.get(Transaction, paid.json()['transaction_id']).amount == 230
    assert seeded.get(TelephonyCall, call.id).redeemed
    assert client.post('/api/v1/checkout/quote', json={'customer_token': call.customer_token, 'bill_amount': 250}).json()['discount'] == 0


def test_declined_pending_and_below_minimum_not_discounted(client, seeded):
    call = accepted_offer(seeded)
    assert client.post('/api/v1/checkout/quote', json={'customer_token': call.customer_token, 'bill_amount': 199.99}).json()['discount'] == 0
    for state in ['ringing', 'declined', 'no_answer']:
        call.accepted = False; call.status = state; seeded.commit()
        assert client.post('/api/v1/checkout/quote', json={'customer_token': call.customer_token, 'bill_amount': 250}).json()['discount'] == 0


def test_two_quotes_cannot_reuse_discount(client, seeded):
    call = accepted_offer(seeded)
    quotes = [client.post('/api/v1/checkout/quote', json={'customer_token': call.customer_token, 'bill_amount': 250}).json() for _ in range(2)]
    assert client.post('/api/v1/checkout/pay', json={'quote_id': quotes[0]['id']}).status_code == 200
    assert client.post('/api/v1/checkout/pay', json={'quote_id': quotes[1]['id']}).status_code == 409
    assert seeded.scalar(select(func.count(Redemption.id)).where(Redemption.campaign_id == call.campaign_id)) == 1


def test_stopped_campaign_expiry_budget_rechecked_at_pay(client, seeded):
    call = accepted_offer(seeded)
    for change in ['stopped', 'expired', 'budget']:
        campaign = seeded.get(Campaign, call.campaign_id)
        campaign.status = 'active'; campaign.end_date = (business_today()+timedelta(days=7)).isoformat(); campaign.budget = 100
        seeded.commit()
        quote = client.post('/api/v1/checkout/quote', json={'customer_token': call.customer_token, 'bill_amount': 250}).json()
        if change == 'stopped': campaign.status = 'stopped'
        if change == 'expired': campaign.end_date = (business_today()-timedelta(days=1)).isoformat()
        if change == 'budget': campaign.budget = 10
        seeded.commit()
        assert client.post('/api/v1/checkout/pay', json={'quote_id': quote['id']}).status_code == 409


def test_checkout_rejects_untrusted_amounts_and_client_discount(client, seeded):
    call = accepted_offer(seeded)
    for bill in [0, -10, 'NaN', 'Infinity', 250.123, 1000001]:
        assert client.post('/api/v1/checkout/quote', json={'customer_token': call.customer_token, 'bill_amount': bill}).status_code == 422
    assert client.post('/api/v1/checkout/quote', json={'customer_token': 'missing', 'bill_amount': 250}).status_code == 404
    assert client.post('/api/v1/checkout/quote', json={'customer_token': call.customer_token, 'bill_amount': 250, 'discount': 200}).status_code == 422
    assert client.post('/api/v1/checkout/pay', json={'quote_id': 'missing', 'payable_amount': 1}).status_code == 422
