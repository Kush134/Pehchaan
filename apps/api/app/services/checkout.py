"""Accepted phone offers flow into a server-priced, single-use demo checkout."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select, func, update
from app.models import Campaign, CampaignAssignment, CustomerToken, Redemption, TelephonyCall, Transaction
from app.models.checkout import RetailCheckout
from app.core.clock import business_today
from app.services.campaigns import money
from app.services.events import emit


def offers(db):
    rows = db.scalars(select(TelephonyCall).order_by(TelephonyCall.created_at.desc()).limit(200)).all()
    return {'items': [{k: getattr(c, k) for k in ('id', 'customer_token', 'customer_name', 'offer_amount', 'minimum_bill', 'status', 'accepted', 'acceptance_source', 'redeemed')} for c in rows]}


def eligible_offer(db, token, bill):
    calls = db.scalars(select(TelephonyCall).where(TelephonyCall.customer_token == token, TelephonyCall.accepted.is_(True), TelephonyCall.redeemed.is_(False)).order_by(TelephonyCall.offer_amount.desc(), TelephonyCall.created_at)).all()
    today = business_today().isoformat()
    for call in calls:
        campaign = db.get(Campaign, call.campaign_id)
        if not campaign or campaign.status != 'active' or not campaign.start_date <= today <= campaign.end_date:
            continue
        assignment = db.scalar(select(CampaignAssignment).where(CampaignAssignment.campaign_id == call.campaign_id, CampaignAssignment.customer_token == token))
        if assignment and db.scalar(select(Redemption).where(Redemption.assignment_id == assignment.id)):
            continue
        spent = db.scalar(select(func.coalesce(func.sum(Redemption.discount), 0)).where(Redemption.campaign_id == campaign.id)) or 0
        if bill >= call.minimum_bill and Decimal(str(spent)) + Decimal(str(call.offer_amount)) <= Decimal(str(campaign.budget)):
            return call
    return None


def quote(db, token, bill_amount):
    customer = db.get(CustomerToken, token)
    if not customer or customer.merchant_id != 'sharma-kirana':
        raise HTTPException(404, 'Customer not found')
    bill = money(bill_amount)
    call = eligible_offer(db, token, bill)
    discount = money(call.offer_amount) if call else 0
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {'customer_token': token, 'bill_amount': bill, 'discount': discount, 'payable_amount': money(bill-discount),
               'offer_id': call.id if call else None, 'eligible': bool(call), 'simulated': True,
               'acceptance_source': call.acceptance_source if call else None,
               'reason': 'Accepted comeback offer applied automatically.' if call else 'No unused accepted offer meets the minimum bill, campaign dates and budget.',
               'expires_at': expires.isoformat()}
    row = RetailCheckout(status='quoted', payload=payload)
    db.add(row); db.flush()
    emit(db, 'checkout.quoted', 'Demo scan priced', f'Bill ₹{bill:g}; discount ₹{discount:g}; payable ₹{payload["payable_amount"]:g}.', agent='payment', data={'checkout_id': row.id, 'simulated': True})
    return serialize(row)


def serialize(row):
    return {**row.payload, 'id': row.id, 'status': row.status, 'created_at': row.created_at.isoformat()}


def pay(db, quote_id):
    row = db.scalar(select(RetailCheckout).where(RetailCheckout.id == quote_id).with_for_update())
    if not row:
        raise HTTPException(404, 'Checkout quote not found')
    if row.status == 'paid':
        return serialize(row)
    claimed_quote = db.execute(update(RetailCheckout).where(RetailCheckout.id == row.id, RetailCheckout.status == 'quoted').values(status='processing'))
    if claimed_quote.rowcount != 1:
        raise HTTPException(409, 'Checkout is already being processed.')
    payload = row.payload
    if datetime.fromisoformat(payload['expires_at']) <= datetime.now(timezone.utc):
        raise HTTPException(409, 'Quote expired. Scan again for a fresh total.')
    call = None
    if payload['offer_id']:
        call = db.scalar(select(TelephonyCall).where(TelephonyCall.id == payload['offer_id']).with_for_update())
        if not call or not call.accepted or call.redeemed:
            raise HTTPException(409, 'Offer was already used or is no longer accepted. Scan again.')
        # Serialize campaign budget checks across different customers in PostgreSQL.
        db.scalar(select(Campaign).where(Campaign.id == call.campaign_id).with_for_update())
        candidate = eligible_offer(db, payload['customer_token'], payload['bill_amount'])
        if not candidate or candidate.id != call.id or money(call.offer_amount) != payload['discount']:
            raise HTTPException(409, 'Offer terms, availability or budget changed. Scan again.')
        claimed = db.execute(update(TelephonyCall).where(TelephonyCall.id == call.id, TelephonyCall.redeemed.is_(False)).values(redeemed=True, checkout_id=row.id))
        if claimed.rowcount != 1:
            raise HTTPException(409, 'Offer was already used. Scan again.')
        assignment = db.scalar(select(CampaignAssignment).where(CampaignAssignment.campaign_id == call.campaign_id, CampaignAssignment.customer_token == call.customer_token))
        if assignment and db.scalar(select(Redemption).where(Redemption.assignment_id == assignment.id)):
            raise HTTPException(409, 'Campaign offer was already redeemed. Scan again.')
        if not assignment:
            assignment = CampaignAssignment(campaign_id=call.campaign_id, customer_token=call.customer_token, variant='Phone', redeemed=False)
            db.add(assignment); db.flush()
        assignment.redeemed = True
        db.add(Redemption(assignment_id=assignment.id, campaign_id=call.campaign_id, discount=payload['discount'], amount=payload['bill_amount']))
    transaction = Transaction(merchant_id='sharma-kirana', customer_token=payload['customer_token'], amount=payload['payable_amount'],
                              gross_profit=money(payload['bill_amount']*.22-payload['discount']), campaign_id=call.campaign_id if call else None,
                              category='Grocery', simulated=True, created_at=datetime.now(timezone.utc))
    db.add(transaction); db.flush()
    row.status = 'paid'
    row.payload = {**payload, 'transaction_id': transaction.id, 'paid_at': datetime.now(timezone.utc).isoformat()}
    from app.analytics.customers import refresh_metrics
    refresh_metrics(db)
    emit(db, 'checkout.paid', 'Simulated customer payment completed', f'₹{payload["bill_amount"]:g} bill − ₹{payload["discount"]:g} offer = ₹{payload["payable_amount"]:g}. No real money moved.', agent='payment', data={'checkout_id': row.id, 'transaction_id': transaction.id, 'simulated': True})
    return serialize(row)
