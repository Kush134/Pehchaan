from datetime import datetime,timedelta,timezone
from app.analytics.customers import calculate_metrics,segment_counts
from app.models import CustomerMetric
from sqlalchemy import select

NOW=datetime(2026,11,14,12,tzinfo=timezone.utc)
def history(days,amount=300):return [{'customer_token':'PK-test','merchant_id':'store','amount':amount,'created_at':NOW-timedelta(days=d)} for d in days]

def test_rfm_calculation():
    metric=calculate_metrics(history([0,5,10,15,20,25]),NOW)[0]
    assert metric['recency_days']==0
    assert metric['frequency']==6
    assert metric['monetary']==1800
    assert metric['average_intervisit_interval']==5

def test_personalized_inactivity_detection():
    metric=calculate_metrics(history(range(17,90,4)),NOW)[0]
    assert metric['customer_segment']=='At-Risk Customers'
    assert metric['risk_score']>75

def test_new_customer_never_lost_regular():
    metric=calculate_metrics(history([12]),NOW)[0]
    assert metric['customer_segment']=='New Customers'
    assert metric['average_intervisit_interval'] is None

def test_spend_decline_uses_comparable_windows():
    rows=history([1,15],100)+history(range(31,60,3),400)
    metric=calculate_metrics(rows,NOW)[0]
    assert metric['customer_segment']=='Declining Customers'
    assert metric['current_30_day_spend']==200
    assert metric['previous_30_day_spend']==4000

def test_seed_has_detectable_segments_and_no_personal_identifiers(seeded):
    counts=segment_counts(seeded)
    assert sum(s['count'] for s in counts)==100
    assert all(s['count']>0 for s in counts)
    metrics=seeded.scalars(select(CustomerMetric)).all()
    assert all(m.customer_token.startswith('PK-') for m in metrics)
    assert all('phone' not in m.payload and 'upi_id' not in m.payload for m in metrics)

def test_seed_never_generates_future_purchases(seeded):
    from app.models import Transaction
    now=datetime.now(timezone.utc)
    for tx in seeded.scalars(select(Transaction)).all():
        timestamp=tx.created_at if tx.created_at.tzinfo else tx.created_at.replace(tzinfo=timezone.utc)
        assert timestamp<=now
