from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import select,func
from app.services.campaigns import validate_offer,create_campaign,launch_campaign,simulate_campaign
from app.models import Transaction

def test_offer_constraint_preserves_margin():
    assert validate_offer(15,250,1000)['expected_gross_profit_per_redemption']==40
    with pytest.raises(ValueError):validate_offer(45,250,1000)
    with pytest.raises(ValueError):validate_offer(15,250,10)

def data():
    today=datetime.now(timezone.utc).date()
    return {'name':'Reproducible comeback','target_segment':'All','offer_amount':15,'minimum_bill':250,'start_date':today.isoformat(),'end_date':(today+timedelta(days=7)).isoformat(),'budget':500,'max_customers':60,'language':'hi-IN','ab_test':True}

def test_campaign_control_budget_and_idempotent_simulation(seeded):
    campaign=create_campaign(seeded,data());id=campaign['id'];launched=launch_campaign(seeded,id)
    assert launched['stats']['allocated']>0 and launched['stats']['control_size']>0
    assert launched['stats']['treatment_size']*20<=500
    first=simulate_campaign(seeded,id);count=seeded.scalar(select(func.count(Transaction.id)))
    second=simulate_campaign(seeded,id)
    assert seeded.scalar(select(func.count(Transaction.id)))==count
    assert first['stats']==second['stats'] and first['stats']['discount_expense']<=500
    assert first['stats']['preliminary']

def test_future_campaign_cannot_generate_redemptions(seeded):
    future=data();future['start_date']='2099-01-01';future['end_date']='2099-01-03'
    campaign=create_campaign(seeded,future);launch_campaign(seeded,campaign['id'])
    from fastapi import HTTPException
    with pytest.raises(HTTPException):simulate_campaign(seeded,campaign['id'])
