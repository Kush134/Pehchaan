from datetime import datetime,timedelta,timezone
import json
import pytest
from app.security.policy import sign_mandate,verify_mandate,validate_policy
from app.services.idempotency import execute_once
from fastapi import HTTPException

def test_hmac_signing_tamper_and_constant_time_verifier():
    payload={'amount':36500,'buyer':'demo'}
    signature=sign_mandate(payload,'test-secret')
    assert verify_mandate(payload,signature,'test-secret')
    assert not verify_mandate(payload|{'amount':95000},signature,'test-secret')
    assert not verify_mandate(payload,signature,'wrong-secret')

@pytest.mark.parametrize('proposal,rule',[
    ({'amount':95000},'BUYER_BUDGET'),({'amount':34000},'MERCHANT_PRICING_MANDATE'),
    ({'amount':36500,'round_number':5},'ROUND_LIMIT'),({'amount':36500,'quantity_available':False},'QUANTITY_AVAILABILITY'),
    ({'amount':36500,'delivery_feasible':False},'DELIVERY_FEASIBILITY'),({'amount':36500,'discount_percent':16},'DISCOUNT_AUTHORIZATION'),
    ({'amount':36500,'operation':'withdraw'},'ALLOWED_OPERATION'),({'amount':36500,'expiry':'2000-01-01T00:00:00+00:00'},'REQUEST_EXPIRY')])
def test_security_policy_rejects_constraints(db,proposal,rule):
    result=validate_policy(db,proposal)
    assert result['status']=='BLOCKED'
    assert {'rule':rule,'passed':False} in result['rules']
    assert '35000' not in json.dumps(result)

def test_valid_quote_pending_required_approvals(db):
    result=validate_policy(db,{'amount':36500})
    assert result['status']=='ELIGIBLE_PENDING_APPROVALS' and result['allowed']

def test_financial_actions_require_signed_mandate(db):
    result=validate_policy(db,{'amount':36500,'operation':'payment','merchant_approved':True,'buyer_confirmed':True})
    assert not result['allowed']
    assert {'rule':'SIGNED_MANDATE_REQUIRED','passed':False} in result['rules']

def test_replay_protection_and_signed_payment(db):
    payload={'amount':36500,'operation':'payment','merchant_approved':True,'buyer_confirmed':True,'nonce':'unique-nonce','expiry':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()}
    payload['signature']=sign_mandate(payload)
    assert validate_policy(db,payload)['status']=='APPROVED';db.commit()
    second=validate_policy(db,payload)
    assert not second['allowed'] and 'Request nonce has already been used.' in second['reasons']

def test_idempotency_detects_mismatched_payload(db):
    calls=[]
    def operation():calls.append(1);return {'id':'created'}
    assert execute_once(db,'key','/test',{'value':1},operation)=={'id':'created'}
    assert execute_once(db,'key','/test',{'value':1},operation)=={'id':'created'}
    assert len(calls)==1
    with pytest.raises(HTTPException) as error:execute_once(db,'key','/test',{'value':2},operation)
    assert error.value.status_code==409
