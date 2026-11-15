from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
from sqlalchemy import select
from fastapi import HTTPException
from app.models import Campaign,CampaignVariant,CampaignAssignment,CustomerMetric,Redemption,Transaction,TelephonyCall
from app.services.events import emit
from app.core.clock import business_today

def money(value): return float(Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))

def validate_offer(offer,minimum,budget):
    offer,minimum,budget=map(lambda x:Decimal(str(x)),(offer,minimum,budget))
    if offer<=0 or minimum<=0 or budget<offer: raise ValueError('Offer and minimum bill must be positive; budget must cover at least one offer.')
    # Seeded merchant average gross margin 22%; preserve an 8% contribution margin.
    if offer>minimum*Decimal('.14'): raise ValueError('Offer exceeds merchant margin mandate: retain at least 8% gross contribution on a 22% margin.')
    return {'expected_gross_profit_per_redemption':money(minimum*Decimal('.22')-offer),'discount_percent':money(offer/minimum*100)}

def create_campaign(db,data:dict):
    validate_offer(data['offer_amount'],data['minimum_bill'],data['budget'])
    if data['start_date']>data['end_date']: raise ValueError('End date must be after start date.')
    campaign=Campaign(merchant_id='sharma-kirana',**data)
    db.add(campaign); db.flush()
    variants=[('A',campaign.offer_amount,campaign.minimum_bill)]
    if campaign.ab_test:
        b_offer=money(campaign.offer_amount+5); b_min=money(campaign.minimum_bill+50)
        validate_offer(b_offer,b_min,campaign.budget)
        variants.append(('B',b_offer,b_min))
    for name,offer,minimum in variants:
        db.add(CampaignVariant(campaign_id=campaign.id,name=name,offer_amount=offer,minimum_bill=minimum))
    emit(db,'campaign.created','Comeback campaign proposal created',campaign.name,agent='comeback',data={'campaign_id':campaign.id})
    return campaign_dict(db,campaign)

def launch_campaign(db,id):
    campaign=db.get(Campaign,id)
    if not campaign: raise HTTPException(404,'Campaign not found')
    if campaign.status=='active': return campaign_dict(db,campaign)
    if campaign.status!='draft': raise HTTPException(409,'Only a draft campaign can be launched')
    if business_today().isoformat()>campaign.end_date: raise HTTPException(422,'Campaign has expired')
    query=select(CustomerMetric)
    if campaign.target_segment not in ('All','All Customers','At-Risk + Declining'):
        query=query.where(CustomerMetric.customer_segment==campaign.target_segment)
    elif campaign.target_segment=='At-Risk + Declining':
        query=query.where(CustomerMetric.customer_segment.in_(['At-Risk Customers','Declining Customers']))
    candidates=list(db.scalars(query).all())
    candidates.sort(key=lambda c:hashlib.sha256(f'{campaign.name}:allocation:{c.customer_token}'.encode()).hexdigest())
    if min(len(candidates),campaign.max_customers)<2: raise HTTPException(422,'At least two eligible customers are required for treatment and control groups')
    variants=list(db.scalars(select(CampaignVariant).where(CampaignVariant.campaign_id==id).order_by(CampaignVariant.name)).all())
    maximum_offer=max(v.offer_amount for v in variants)
    # Reserve budget against every non-control assignment, not expected conversions.
    treatment_capacity=int(Decimal(str(campaign.budget))//Decimal(str(maximum_offer)))
    total=min(campaign.max_customers,len(candidates),max(1,int(treatment_capacity/0.8)))
    treatment_count=0
    for index,customer in enumerate(candidates[:total]):
        variant='Control' if index%5==0 else variants[(index//1)%len(variants)].name
        if variant!='Control':
            if treatment_count>=treatment_capacity: continue
            treatment_count+=1
        db.add(CampaignAssignment(campaign_id=id,customer_token=customer.customer_token,variant=variant))
    campaign.status='active'; db.flush()
    emit(db,'campaign.launched','Merchant approved offer',f'{total} pseudonymous customers allocated with a reproducible control group.',agent='comeback',data={'campaign_id':id,'allocated':total})
    return campaign_dict(db,campaign)

def simulate_campaign(db,id):
    campaign=db.get(Campaign,id)
    if not campaign: raise HTTPException(404,'Campaign not found')
    if campaign.status!='active': raise HTTPException(409,'Launch the campaign before simulating redemptions')
    today=business_today().isoformat()
    if not campaign.start_date<=today<=campaign.end_date: raise HTTPException(422,'Campaign is outside its active date range')
    assignments=db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id==id)).all()
    variants={v.name:v for v in db.scalars(select(CampaignVariant).where(CampaignVariant.campaign_id==id).order_by(CampaignVariant.name)).all()}
    phone_customers=set(db.scalars(select(TelephonyCall.customer_token).where(TelephonyCall.campaign_id==id)).all())
    new=0
    for assignment in assignments:
        # Phone offers are redeemed only through accepted-offer checkout.
        if assignment.customer_token in phone_customers: continue
        existing=db.scalar(select(Redemption).where(Redemption.assignment_id==assignment.id))
        if existing: continue
        value=int(hashlib.sha256(f'{campaign.name}:redemption:{assignment.customer_token}'.encode()).hexdigest()[:8],16)/0xffffffff
        chance=.19 if assignment.variant=='Control' else (.55 if assignment.variant=='A' else .61)
        if value>=chance: continue
        variant=variants.get(assignment.variant)
        discount=variant.offer_amount if variant else 0
        minimum=variant.minimum_bill if variant else campaign.minimum_bill
        bill=money(minimum+int(value*137)%135)
        assignment.redeemed=True
        db.add(Redemption(assignment_id=assignment.id,campaign_id=id,discount=discount,amount=bill))
        db.add(Transaction(merchant_id='sharma-kirana',customer_token=assignment.customer_token,amount=money(bill-discount),gross_profit=money(bill*.22-discount),category='Grocery',campaign_id=id,created_at=datetime.now(timezone.utc),simulated=True))
        new+=1
    db.flush()
    emit(db,'campaign.redemptions','Campaign simulation completed',f'{new} new synthetic purchases recorded. All results are demo observations.',agent='analytics',data={'campaign_id':id,'new_redemptions':new})
    return campaign_dict(db,campaign)

def campaign_dict(db,campaign):
    variants=db.scalars(select(CampaignVariant).where(CampaignVariant.campaign_id==campaign.id)).all()
    assignments=db.scalars(select(CampaignAssignment).where(CampaignAssignment.campaign_id==campaign.id)).all()
    redemptions=db.scalars(select(Redemption).where(Redemption.campaign_id==campaign.id)).all()
    by_assignment={r.assignment_id:r for r in redemptions}
    treatment=[a for a in assignments if a.variant!='Control']; control=[a for a in assignments if a.variant=='Control']
    tr=sum(a.redeemed for a in treatment); cr=sum(a.redeemed for a in control)
    treatment_rate=tr/len(treatment) if treatment else 0; control_rate=cr/len(control) if control else 0
    t_profit=sum(by_assignment[a.id].amount*.22-by_assignment[a.id].discount for a in treatment if a.id in by_assignment)
    c_profit=sum(by_assignment[a.id].amount*.22 for a in control if a.id in by_assignment)
    increment=t_profit-(c_profit/len(control)*len(treatment) if control else 0)
    from scipy.stats import fisher_exact
    p_value=float(fisher_exact([[tr,len(treatment)-tr],[cr,len(control)-cr]]).pvalue) if treatment and control else 1.0
    has_phone=any(a.variant=='Phone' for a in assignments)
    preliminary=has_phone or len(treatment)<30 or len(control)<20 or tr+cr<20 or p_value>=.05
    return {k:getattr(campaign,k) for k in ('id','name','target_segment','offer_amount','minimum_bill','start_date','end_date','budget','max_customers','language','ab_test','status')}|{'created_at':campaign.created_at.isoformat(),'variants':[{'id':v.id,'name':v.name,'offer_amount':v.offer_amount,'minimum_bill':v.minimum_bill} for v in variants],'stats':{'allocated':len(assignments),'redeemed':tr,'returning_customers':tr,'discount_expense':money(sum(r.discount for r in redemptions)),'conversion_rate':round(treatment_rate*100,1),'incremental_gross_profit':money(increment),'control_conversion_rate':round(control_rate*100,1),'treatment_conversion_rate':round(treatment_rate*100,1),'preliminary':preliminary,'p_value':round(p_value,5),'evidence':('Includes manually contacted phone recipients; not a randomized causal estimate' if has_phone else 'Preliminary estimate; sample sizes or statistical evidence are insufficient') if preliminary else 'Observed synthetic randomized experiment; two-sided Fisher p < 0.05, treatment n >= 30, control n >= 20','treatment_size':len(treatment),'control_size':len(control),'control_returns':cr},'assignments':[{'customer_token':a.customer_token,'variant':a.variant,'redeemed':a.redeemed} for a in assignments]}
