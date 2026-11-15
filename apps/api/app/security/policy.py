"""Deterministic policy enforcement. Private seller floors never enter API payloads."""
import hashlib
import hmac
import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.core.config import signing_secret
from app.models import PolicyDecision, ReplayNonce, uid, now
from app.services.events import emit

PRIVATE_DEMO_FLOORS={'seller-a':Decimal('35000'),'seller-b':Decimal('35000'),'seller-c':Decimal('35000')}
ALLOWED_OPERATIONS={'quote','confirm_order','payment','campaign','settlement','validate'}

def sign_mandate(payload:dict, secret:str|None=None)->str:
    canonical=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return hmac.new((secret or signing_secret).encode(),canonical,hashlib.sha256).hexdigest()

def verify_mandate(payload:dict,signature:str,secret:str|None=None)->bool:
    return isinstance(signature,str) and hmac.compare_digest(sign_mandate(payload,secret),signature)

def validate_policy(db, proposal:dict, floor:float|Decimal|None=None):
    amount=Decimal(str(proposal.get('amount',proposal.get('total_amount',0))))
    budget=Decimal(str(proposal.get('budget',40000)))
    if not amount.is_finite() or not budget.is_finite(): raise ValueError('Amounts must be finite')
    seller_id=proposal.get('seller_id','seller-a')
    minimum=Decimal(str(floor)) if floor is not None else PRIVATE_DEMO_FLOORS.get(seller_id,Decimal('35000'))
    rules=[]; reasons=[]
    def check(name,passed,message):
        rules.append({'rule':name,'passed':bool(passed)})
        if not passed: reasons.append(message)
    check('KNOWN_SELLER',seller_id in PRIVATE_DEMO_FLOORS or floor is not None,'Seller is not authorized by this mandate.')
    check('BUYER_BUDGET',amount>0 and budget>0 and amount<=budget,'Proposed amount exceeds the authorized buyer budget or is invalid.')
    check('MERCHANT_PRICING_MANDATE',amount>=minimum,'Proposed offer violates merchant pricing mandate.')
    check('DISCOUNT_AUTHORIZATION',Decimal(str(proposal.get('discount_percent',0)))<=min(Decimal('15'),Decimal(str(proposal.get('max_discount_percent',15)))) and Decimal(str(proposal.get('discount_percent',0)))>=0,'Discount exceeds merchant authorization.')
    check('QUANTITY_AVAILABILITY',proposal.get('quantity_available',True),'Requested quantity is unavailable.')
    check('DELIVERY_FEASIBILITY',proposal.get('delivery_feasible',True),'Requested delivery cannot be fulfilled.')
    operation=proposal.get('operation','quote')
    check('ALLOWED_OPERATION',operation in ALLOWED_OPERATIONS,'Operation is not permitted by this mandate.')
    check('ROUND_LIMIT',1<=int(proposal.get('round_number',1))<=4,'Maximum of four negotiation rounds exceeded.')
    expiry=proposal.get('expiry')
    if expiry:
        try:
            expires=datetime.fromisoformat(str(expiry).replace('Z','+00:00'))
            if expires.tzinfo is None: expires=expires.replace(tzinfo=timezone.utc)
            valid_expiry=expires>now()
        except ValueError: valid_expiry=False
        check('REQUEST_EXPIRY',valid_expiry,'Request mandate has expired.')
    else: check('REQUEST_EXPIRY',True,'')
    nonce=proposal.get('nonce'); signature=proposal.get('signature')
    if signature:
        signed={k:v for k,v in proposal.items() if k!='signature'}
        check('MANDATE_SIGNATURE',verify_mandate(signed,signature),'Mandate signature is invalid.')
    else: check('MANDATE_SIGNATURE',True,'')
    if nonce:
        replayed=db.get(ReplayNonce,nonce) is not None
        check('REPLAY_PROTECTION',not replayed,'Request nonce has already been used.')
        if not replayed and not reasons:
            try:
                with db.begin_nested():
                    db.add(ReplayNonce(nonce=nonce)); db.flush()
            except IntegrityError:
                check('REPLAY_PROTECTION',False,'Request nonce has already been used.')
    else: check('REPLAY_PROTECTION',True,'')
    approvals=bool(proposal.get('merchant_approved')) and bool(proposal.get('buyer_confirmed'))
    if operation in {'confirm_order','payment','settlement'}:
        check('SIGNED_MANDATE_REQUIRED',bool(expiry and nonce and signature),'A signed, expiring server mandate with replay protection is required.')
        check('MERCHANT_APPROVAL',bool(proposal.get('merchant_approved')),'Merchant approval is required.')
        check('BUYER_CONFIRMATION',bool(proposal.get('buyer_confirmed')),'Buyer confirmation is required.')
    state='BLOCKED' if reasons else ('APPROVED' if approvals else 'ELIGIBLE_PENDING_APPROVALS')
    payload={'id':uid(),'status':state,'allowed':not reasons,'reasons':reasons,'rules':rules,'amount':float(amount),'budget':float(budget),'created_at':now().isoformat()}
    db.add(PolicyDecision(id=payload['id'],status=state,payload=payload))
    emit(db,'firewall.blocked' if reasons else 'firewall.validated','Mandate firewall blocked proposal' if reasons else 'Proposal passed mandate validation',reasons[0] if reasons else 'Eligible within budget and seller policy; required approvals remain enforced.',agent='firewall',data={'decision_id':payload['id'],'amount':float(amount),'status':state},status='blocked' if reasons else 'success')
    return payload
