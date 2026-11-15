from datetime import datetime, timezone
import numpy as np
import pandas as pd
from sqlalchemy import select, delete
from app.models import Transaction, CustomerMetric

SEGMENT_COLORS = {'Champions':'#35c6a4','Loyal Customers':'#4f92f4','Potential Loyalists':'#94a3fa','New Customers':'#8b9db5','At-Risk Customers':'#e9b44c','Lost Customers':'#ef7585','Declining Customers':'#cb8df2'}

def calculate_metrics(transactions: list[dict], reference: datetime | None = None) -> list[dict]:
    reference = reference or datetime.now(timezone.utc)
    if not transactions: return []
    frame = pd.DataFrame(transactions)
    frame['created_at'] = pd.to_datetime(frame['created_at'], utc=True)
    ref = pd.Timestamp(reference)
    result=[]
    for token, rows in frame.groupby('customer_token'):
        rows=rows.sort_values('created_at')
        dates=rows.created_at.drop_duplicates()
        gaps=dates.diff().dt.total_seconds().dropna().to_numpy()/86400
        mean=float(np.mean(gaps)) if len(gaps) else None
        std=float(np.std(gaps)) if len(gaps) else 0
        recency=max(0,(ref-dates.iloc[-1]).total_seconds()/86400)
        tenure=max(0,(ref-dates.iloc[0]).days)
        previous=rows[(rows.created_at>=ref-pd.Timedelta(days=60))&(rows.created_at<ref-pd.Timedelta(days=30))]
        current=rows[rows.created_at>=ref-pd.Timedelta(days=30)]
        previous_spend=float(previous.amount.sum()); current_spend=float(current.amount.sum())
        count=len(rows); total=float(rows.amount.sum()); avg=total/count
        enough=count>=5 and tenure>=21 and mean is not None
        inactive=enough and recency>max(mean*2,mean+2*std,7)
        lost=enough and recency>max(mean*4,35)
        declining=enough and len(previous)>=3 and current_spend<previous_spend*.55 and recency<35
        if tenure<=14 and count<=3: segment='New Customers'
        elif lost: segment='Lost Customers'
        elif inactive: segment='At-Risk Customers'
        elif declining: segment='Declining Customers'
        elif count>=20 and total>=6500: segment='Champions'
        elif count>=10: segment='Loyal Customers'
        else: segment='Potential Loyalists'
        risk=min(100,round((recency/max(mean or 30,1))*28 + (25 if declining else 0),1)) if enough else 5.0
        if segment in ('Champions','Loyal Customers'): risk=min(risk,25)
        result.append({'customer_token':str(token),'merchant_id':str(rows.merchant_id.iloc[0]),'total_transactions':count,'lifetime_spend':round(total,2),'average_transaction_value':round(avg,2),'last_transaction_date':dates.iloc[-1].isoformat(),'first_transaction_date':dates.iloc[0].isoformat(),'average_intervisit_interval':round(mean,1) if mean else None,'intervisit_standard_deviation':round(std,1),'previous_30_day_spend':round(previous_spend,2),'current_30_day_spend':round(current_spend,2),'customer_segment':segment,'risk_score':risk,'estimated_lost_revenue':round(max(0,(previous_spend-current_spend)),2),'recency_days':round(recency),'frequency':count,'monetary':round(total,2)})
    return result

def refresh_metrics(db):
    txs=db.scalars(select(Transaction)).all()
    data=[{'customer_token':t.customer_token,'merchant_id':t.merchant_id,'amount':t.amount,'created_at':t.created_at} for t in txs]
    metrics=calculate_metrics(data)
    db.execute(delete(CustomerMetric))
    for m in metrics:
        db.add(CustomerMetric(customer_token=m['customer_token'],merchant_id=m['merchant_id'],customer_segment=m['customer_segment'],risk_score=m['risk_score'],payload=m))
    db.flush()
    return metrics

def segment_counts(db):
    metrics=db.scalars(select(CustomerMetric)).all()
    return [{'segment':name,'count':sum(x.customer_segment==name for x in metrics),'color':color} for name,color in SEGMENT_COLORS.items()]
