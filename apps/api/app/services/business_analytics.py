"""Evidence-based merchant analytics; item detail comes only from recorded baskets.

Historical aggregate transactions cannot identify products or queue waiting times.
Forecasts are transparent statistical estimates, never promises or LLM guesses.
"""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
from itertools import combinations
from statistics import mean, linear_regression

from sqlalchemy import select

from app.core.clock import MERCHANT_TIMEZONE, business_today
from app.models import Product, Transaction
from app.services.campaigns import money


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def day_start(day):
    return datetime.combine(day,time.min,tzinfo=MERCHANT_TIMEZONE).astimezone(timezone.utc)


def fit_predict(values,offset=1):
    if len(values)<2 or len(set(values))==1:
        return max(0,mean(values)) if values else 0
    slope,intercept=linear_regression(range(len(values)),values)
    return max(0,intercept+slope*(len(values)-1+offset))


def revenue_forecast(transactions,today=None):
    today=today or business_today()
    completed=[tx for tx in transactions if aware(tx.created_at).astimezone(MERCHANT_TIMEZONE).date()<today]
    earliest=min((aware(tx.created_at).astimezone(MERCHANT_TIMEZONE).date() for tx in completed),default=today)
    first=max(today-timedelta(days=56),earliest)
    daily=defaultdict(float)
    for tx in completed:
        daily[aware(tx.created_at).astimezone(MERCHANT_TIMEZONE).date()]+=tx.amount
    values=[daily[first+timedelta(days=i)] for i in range(max(0,(today-first).days))]
    nonzero=sum(value>0 for value in values)
    has_evidence=len(values)>=14 and nonzero>=7
    prediction=lambda offset:fit_predict(values,offset) if has_evidence else (mean(values[-7:]) if values else 0)
    backtest=[]
    if has_evidence and len(values)>=21:
        for index in range(len(values)-7,len(values)):
            backtest.append(abs(fit_predict(values[:index])-values[index]))
    return {'daily':[{'date':(today+timedelta(days=i)).isoformat(),'revenue':money(prediction(i+1))} for i in range(7)],
            'method':'ordinary_least_squares_daily_revenue' if has_evidence else 'recent_mean_sparse_fallback',
            'is_ml':has_evidence,'sample_days':len(values),'nonzero_days':nonzero,
            'training_start':first.isoformat() if values else None,
            'training_end':(today-timedelta(days=1)).isoformat() if values else None,
            'backtest_mae':money(mean(backtest)) if backtest else None,
            'backtest_method':'7-day rolling-origin, one-day-ahead holdout; MAE in rupees' if backtest else 'Unavailable: need at least 21 complete days and 7 nonzero days',
            'limitations':['A simple linear revenue trend, with no seasonality, holidays, weather or causal claims.',
                           'Today is excluded from training because the trading day is incomplete.',
                           'Fewer than 14 complete days or 7 active days uses a recent-mean fallback.',
                           'Missing transaction days are treated as zero recorded sales, not confirmed store closures.']}


def business_summary(db,days=7):
    from app.models.retail import RetailSale, RetailSaleLine, StockBatch
    today=business_today();now=datetime.now(timezone.utc)
    start_day=today-timedelta(days=days-1);start=day_start(start_day)
    previous_start=day_start(start_day-timedelta(days=days))
    # Restrict every view to this merchant and exclude future-dated records.
    history=list(db.scalars(select(Transaction).where(Transaction.merchant_id=='sharma-kirana',
                Transaction.created_at>=min(previous_start,day_start(today-timedelta(days=56))),Transaction.created_at<=now)).all())
    current=[row for row in history if aware(row.created_at)>=start]
    previous=[row for row in history if previous_start<=aware(row.created_at)<start]
    revenue=money(sum(row.amount for row in current));gross_profit=money(sum(row.gross_profit for row in current))
    previous_revenue=money(sum(row.amount for row in previous))
    sales=list(db.scalars(select(RetailSale).where(RetailSale.created_at>=start,RetailSale.created_at<=now)).all())
    sale_ids=[sale.id for sale in sales]
    lines=list(db.scalars(select(RetailSaleLine).where(RetailSaleLine.sale_id.in_(sale_ids))).all()) if sale_ids else []
    products=list(db.scalars(select(Product).where(Product.merchant_id=='sharma-kirana').order_by(Product.name)).all())
    product_map={product.id:product for product in products}
    # Sale-line name, price and cost are snapshots; current catalogue changes do not rewrite history.
    grouped={}
    baskets=defaultdict(set)
    for line in lines:
        if line.product_id not in product_map:
            continue
        key=line.product_id
        item=grouped.setdefault(key,{'product_id':key,'name':line.product_name,'variant':line.variant,
                                     'quantity':0,'revenue':0,'gross_profit':0})
        item['quantity']+=line.quantity;item['revenue']+=line.line_total;item['gross_profit']+=line.line_profit
        baskets[line.sale_id].add(key)
    best_sellers=sorted([{**item,'revenue':money(item['revenue']),'gross_profit':money(item['gross_profit'])} for item in grouped.values()],
                        key=lambda item:(-item['quantity'],-item['revenue'],item['product_id']))
    pairs=Counter(pair for basket in baskets.values() for pair in combinations(sorted(basket),2))
    combinations_list=[{'products':[{'id':key,'name':product_map[key].name,'variant':product_map[key].variant} for key in pair],
                        'basket_count':count} for pair,count in pairs.most_common(10)]
    low_stock=[{'product_id':p.id,'name':p.name,'variant':p.variant,'quantity':p.available_stock,
                'reorder_point':p.reorder_point,'suggested_quantity':max(1,p.reorder_point*2-p.available_stock),
                'unit':p.unit,'supplier':p.supplier} for p in products if p.available_stock<=p.reorder_point]
    batches=list(db.scalars(select(StockBatch).where(StockBatch.product_id.in_(list(product_map)),StockBatch.quantity_remaining>0,
                             StockBatch.expires_on.is_not(None),StockBatch.expires_on<=today+timedelta(days=14))
                             .order_by(StockBatch.expires_on)).all()) if products else []
    expiry=[{'id':batch.id,'product_id':batch.product_id,'name':product_map[batch.product_id].name,
             'variant':product_map[batch.product_id].variant,'batch_number':batch.batch_number,'quantity':batch.quantity_remaining,
             'expires_on':batch.expires_on.isoformat(),'days_remaining':(batch.expires_on-today).days,
             'cost_at_risk':money(batch.quantity_remaining*batch.cost_price)} for batch in batches]
    expiring=[batch for batch in expiry if batch['days_remaining']>=0];expired=[batch for batch in expiry if batch['days_remaining']<0]
    # Root finance service supplies this model; expense dates follow merchant-local calendar dates.
    from app.models.finance import Expense
    expenses=list(db.scalars(select(Expense).where(Expense.expense_date>=start_day,Expense.expense_date<=today)).all())
    expense_total=money(sum(expense.amount for expense in expenses))
    growth=(revenue/previous_revenue-1) if previous_revenue else None
    components=[
        {'name':'Sales','score':round(max(0,min(100,50+growth*50)),1) if growth is not None else None,'weight':.3,
         'available':growth is not None,'evidence':f'₹{revenue:,.2f} recorded revenue versus ₹{previous_revenue:,.2f} in the previous {days} days.',
         'method':'50 + 50 × period growth, bounded 0–100; missing baseline is excluded.'},
        {'name':'Margin','score':round(max(0,min(100,gross_profit/revenue/.22*100)),1) if revenue else None,'weight':.3,
         'available':bool(revenue),'evidence':f'₹{gross_profit:,.2f} recorded gross profit on ₹{revenue:,.2f} revenue.',
         'method':'Recorded gross margin ÷ 22% reference margin × 100, bounded 0–100.'},
        {'name':'Inventory','score':round((1-len(low_stock)/len(products))*100,1) if products else None,'weight':.25,
         'available':bool(products),'evidence':f'{len(low_stock)} of {len(products)} catalogue products are at or below their reorder point.',
         'method':'Percentage of catalogue products above their reorder point.'},
        {'name':'Expenses','score':round(max(0,min(100,(1-expense_total/gross_profit)*100)),1) if expenses and gross_profit>0 else None,'weight':.15,
         'available':bool(expenses and gross_profit>0),'evidence':f'{len(expenses)} recorded expenses total ₹{expense_total:,.2f}.',
         'method':'(Gross profit − recorded expenses) ÷ gross profit × 100; no expense records is missing evidence.'},
    ]
    available=[component for component in components if component['available']]
    score=round(sum(component['score']*component['weight'] for component in available)/sum(component['weight'] for component in available),1) if available else None
    hours=defaultdict(lambda:{'transactions':0,'revenue':0})
    for tx in current:
        hour=aware(tx.created_at).astimezone(MERCHANT_TIMEZONE).hour
        hours[hour]['transactions']+=1;hours[hour]['revenue']+=tx.amount
    peak_hours=[{'hour':hour,'label':f'{hour:02}:00–{hour+1:02}:00 IST','transactions':values['transactions'],
                 'revenue':money(values['revenue'])} for hour,values in sorted(hours.items(),key=lambda item:(-item[1]['transactions'],item[0]))]
    insights=[]
    if best_sellers:
        top=best_sellers[0]
        insights.append({'what':f'{top["name"]} leads recorded item sales.',
            'evidence':f'{top["quantity"]:g} units, ₹{top["revenue"]:,.2f} revenue in {days} days; line-item baskets only.',
            'why':'A frequently purchased product deserves enough shelf stock.',
            'action':'Check this product’s stock and review its supplier reorder before replenishing.',
            'expected_benefit':'May reduce missed sales; no revenue uplift is guaranteed.'})
    if low_stock:
        insights.append({'what':f'{len(low_stock)} products need a stock review.',
            'evidence':'; '.join(f'{item["name"]}: {item["quantity"]} left, reorder point {item["reorder_point"]}' for item in low_stock[:3]),
            'why':'Available stock is at or below the merchant’s configured reorder level.',
            'action':'Review a supplier reorder, then explicitly approve receipt when stock arrives.',
            'expected_benefit':'May prevent stockouts; supplier delivery is not assumed.'})
    if expiry:
        insights.append({'what':f'{len(expiring)} batches expire within 14 days; {len(expired)} are already expired.',
            'evidence':'; '.join(f'{item["name"]}, batch {item["batch_number"]}, expires {item["expires_on"]}' for item in expiry[:3]),
            'why':'Unsold dated stock can become a loss and expired stock must not be sold.',
            'action':'Use first-expiry-first-out for valid stock and remove expired batches from sale.',
            'expected_benefit':f'₹{money(sum(item["cost_at_risk"] for item in expiry)):,.2f} recorded batch cost is flagged for review, not a forecast loss.'})
    if not insights:
        insights.append({'what':'More recorded detail is needed for product recommendations.',
            'evidence':f'{len(current)} aggregate transactions and {len(sales)} itemized sales in this period.',
            'why':'A transaction total alone cannot reveal which products sold together.',
            'action':'Record sales with product line items and stock batches.',
            'expected_benefit':'Future best-seller and expiry answers will use actual basket evidence.'})
    summary=f'Last {days} day(s): ₹{revenue:,.2f} revenue, ₹{gross_profit:,.2f} gross profit, ₹{expense_total:,.2f} recorded expenses; ₹{money(gross_profit-expense_total):,.2f} after recorded expenses. {len(low_stock)} low-stock products; {len(expiring)} batches expire within 14 days.'
    return {'period':{'days':days,'start':start_day.isoformat(),'end':today.isoformat(),'timezone':'Asia/Kolkata'},
        'sales':{'revenue':revenue,'gross_profit':gross_profit,'previous_revenue':previous_revenue,
                 'revenue_change_percent':round(growth*100,1) if growth is not None else None,
                 'transactions':len(current),'units_sold':sum(item['quantity'] for item in best_sellers),'line_item_sales':len(sales),
                 'expenses':expense_total,'expense_count':len(expenses),'net_profit':money(gross_profit-expense_total),
                 'line_item_coverage_notice':'Product rankings and combinations use recorded retail sale lines only. Older aggregate transactions have no item identity.',
                 'profit_notice':'Gross profit uses stored sale costs. Net profit subtracts recorded expenses only; unrecorded expenses are unknown.'},
        'best_sellers':best_sellers[:10],'inventory':{'low_stock':low_stock,'expiring':expiring,'expired':expired},
        'health':{'score':score,'components':components,'method':'Available-evidence weighted heuristic; weights are renormalized when evidence is missing.',
                  'limitations':['Informational score, not a credit score or business valuation.','Absent expense records do not mean zero operating cost.']},
        'forecast':revenue_forecast(history,today),'product_combinations':combinations_list,'peak_hours':peak_hours,
        'wait_times':{'available':False,'reason':'No customer arrival, queue or service-start timestamps are recorded. Transaction times cannot establish waiting time.'},
        'insights':insights,'summary_text':summary,'generated_at':now.isoformat(),'data_notice':'Local demonstration records; financial entries and itemized demo seed are labeled synthetic.'}
