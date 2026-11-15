import asyncio,csv,io,json
from datetime import datetime,timezone,timedelta
from collections import defaultdict
from fastapi import APIRouter,Depends,HTTPException,Query,Request,UploadFile,File
from fastapi.responses import StreamingResponse, Response
from pydantic import ValidationError
from sqlalchemy import select,func,text
from app.database.session import get_db,SessionLocal
from app.models import *
from app.core.config import settings
from app.analytics.customers import segment_counts,refresh_metrics
from app.analytics.detail import customer_detail,weekly_cohorts
from app.schemas.core import CampaignCreate,ProductWrite,FirewallProposal
from app.services.campaigns import create_campaign,launch_campaign,simulate_campaign,campaign_dict,money
from app.services.events import emit,recent_events,event_dict,redis_status
from app.services.idempotency import execute_once
from app.security.policy import validate_policy

router=APIRouter()

def merchant_role(request:Request):
    # Explicit local hackathon role, not production authentication.
    role=request.headers.get('X-Demo-Role','merchant')
    if role!='merchant': raise HTTPException(403,'This operation requires the merchant demo role')

def mutate(db,request,payload,fn):
    try:
        result=execute_once(db,request.headers.get('Idempotency-Key'),request.url.path,payload,fn)
        db.commit();return result
    except ValueError as error:
        db.rollback();raise HTTPException(422,str(error))
    except Exception:
        db.rollback();raise

@router.get('/health')
def health(db=Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status':'ok','demo_mode':settings.demo_mode,'database':'postgresql' if db.bind.dialect.name=='postgresql' else 'sqlite','redis':redis_status(),'sarvam':{'configured':bool(settings.sarvam_api_key),'chat_model':settings.sarvam_chat_model,'stt_model':settings.sarvam_stt_model,'tts_model':settings.sarvam_tts_model},'payment_provider':'simulated'}

@router.get('/customers')
def customers(segment:str='All',search:str='',page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db=Depends(get_db)):
    query=select(CustomerMetric)
    if segment not in ('All','All Customers'):query=query.where(CustomerMetric.customer_segment==segment)
    if search:query=query.where(CustomerMetric.customer_token.ilike(f'%{search[:100]}%'))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    items=db.scalars(query.order_by(CustomerMetric.risk_score.desc(),CustomerMetric.customer_token).offset((page-1)*page_size).limit(page_size)).all()
    return {'items':[m.payload for m in items],'total':total,'page':page,'page_size':page_size}

@router.get('/customers/segments')
def segments(db=Depends(get_db)):return segment_counts(db)

@router.get('/customers/at-risk')
def at_risk(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db=Depends(get_db)):
    query=select(CustomerMetric).where(CustomerMetric.customer_segment.in_(['At-Risk Customers','Declining Customers','Lost Customers']))
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    items=db.scalars(query.order_by(CustomerMetric.risk_score.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return {'items':[m.payload for m in items],'total':total,'page':page,'page_size':page_size}

@router.get('/customers/{token}')
def customer_profile(token:str,db=Depends(get_db)):
    return customer_detail(db,token)

@router.post('/customers/recalculate',dependencies=[Depends(merchant_role)])
def recalculate(request:Request,db=Depends(get_db)):
    def run():
        data=refresh_metrics(db);emit(db,'analytics.updated','Customer segments updated','RFM, cadence and merchant spend decline recalculated.',agent='customer-intelligence');return {'updated':len(data)}
    return mutate(db,request,{},run)

@router.get('/campaigns')
def campaigns(db=Depends(get_db)):
    return [campaign_dict(db,c) for c in db.scalars(select(Campaign).order_by(Campaign.created_at.desc())).all()]

@router.post('/campaigns',dependencies=[Depends(merchant_role)])
def campaign_create(body:CampaignCreate,request:Request,db=Depends(get_db)):
    data=body.model_dump(mode='json')
    return mutate(db,request,data,lambda:create_campaign(db,data))

@router.post('/campaigns/{id}/launch',dependencies=[Depends(merchant_role)])
def campaign_launch(id:str,request:Request,db=Depends(get_db)):
    from app.services.notifications import queue_campaign_call, dispatch_call
    def run():
        campaign=launch_campaign(db,id)
        call=queue_campaign_call(db,id)
        return campaign|{'call_id':call.id}
    # Commit the campaign, durable call and idempotency receipt before dialing.
    result=mutate(db,request,{},run)
    call=dispatch_call(db,result['call_id'])
    return result|{'call':call}

@router.post('/campaigns/{id}/simulate-redemptions',dependencies=[Depends(merchant_role)])
def campaign_simulate(id:str,request:Request,db=Depends(get_db)):
    def run():
        data=simulate_campaign(db,id);refresh_metrics(db);return data
    return mutate(db,request,{},run)

@router.post('/campaigns/{id}/stop',dependencies=[Depends(merchant_role)])
def campaign_stop(id:str,request:Request,db=Depends(get_db)):
    def run():
        campaign=db.get(Campaign,id)
        if not campaign:raise HTTPException(404,'Campaign not found')
        campaign.status='stopped';emit(db,'campaign.stopped','Demo campaign stopped',campaign.name,agent='comeback');return campaign_dict(db,campaign)
    return mutate(db,request,{},run)

@router.get('/catalog/products',dependencies=[Depends(merchant_role)])
def products(db=Depends(get_db)):return [product_dict(p) for p in db.scalars(select(Product).order_by(Product.name)).all()]

def product_dict(p):return {k:getattr(p,k) for k in ('id','name','category','unit','selling_price','available_stock','purchase_price','minimum_selling_price','supplier')}|{'updated_at':p.updated_at.isoformat()}

@router.post('/catalog/products',dependencies=[Depends(merchant_role)])
def product_create(body:ProductWrite,request:Request,db=Depends(get_db)):
    def run():
        p=Product(merchant_id='sharma-kirana',**body.model_dump());db.add(p);db.flush();db.add(Inventory(product_id=p.id,quantity=p.available_stock));emit(db,'catalog.created','Product added to catalogue',p.name,agent='merchant');return product_dict(p)
    return mutate(db,request,body.model_dump(),run)

@router.patch('/catalog/products/{id}',dependencies=[Depends(merchant_role)])
async def product_update(id:str,request:Request,db=Depends(get_db)):
    payload=await request.json()
    def run():
        p=db.get(Product,id)
        if not p:raise HTTPException(404,'Product not found')
        existing={k:getattr(p,k) for k in ProductWrite.model_fields}
        try:data=ProductWrite.model_validate(existing|payload).model_dump()
        except ValidationError as e:raise HTTPException(422,str(e))
        new_stock=data.pop('available_stock')
        if new_stock!=p.available_stock:
            from app.services.retail import adjust_stock
            adjust_stock(db,{'product_id':p.id,'quantity_delta':new_stock-p.available_stock,'reason':'Catalogue stock correction'})
        for key,value in data.items():setattr(p,key,value)
        inv=db.scalar(select(Inventory).where(Inventory.product_id==id))
        if inv:inv.quantity=p.available_stock
        p.updated_at=now();emit(db,'catalog.updated','Product catalogue updated',p.name,agent='merchant');return product_dict(p)
    return mutate(db,request,payload,run)

@router.delete('/catalog/products/{id}',dependencies=[Depends(merchant_role)])
def product_delete(id:str,request:Request,db=Depends(get_db)):
    def run():
        p=db.get(Product,id)
        if not p:raise HTTPException(404,'Product not found')
        from app.models.retail import RetailSaleLine,StockMovement,StockBatch
        if db.scalar(select(RetailSaleLine.id).where(RetailSaleLine.product_id==id).limit(1)):raise HTTPException(409,'This product has sale history and must be retained. Set stock to zero to archive it.')
        db.query(StockMovement).filter(StockMovement.product_id==id).delete();db.query(StockBatch).filter(StockBatch.product_id==id).delete();db.query(Inventory).filter(Inventory.product_id==id).delete();db.delete(p);emit(db,'catalog.deleted','Product removed',p.name,agent='merchant');return {'deleted':id}
    return mutate(db,request,{},run)

@router.post('/catalog/import',dependencies=[Depends(merchant_role)])
async def catalog_import(request:Request,file:UploadFile=File(...),db=Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith('.csv'):raise HTTPException(422,'Upload a CSV file')
    raw=await file.read(settings.max_upload_bytes+1)
    if len(raw)>settings.max_upload_bytes:raise HTTPException(413,'File exceeds 10 MB upload limit')
    try:
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        if not rows or len(rows)>1000:raise ValueError('CSV must contain between 1 and 1000 rows')
        validated=[ProductWrite.model_validate(row).model_dump() for row in rows]
    except (UnicodeDecodeError,ValueError,ValidationError) as error:raise HTTPException(422,f'Invalid catalogue CSV: {str(error)[:500]}')
    def run():
        items=[]
        for data in validated:
            p=Product(merchant_id='sharma-kirana',**data);db.add(p);db.flush();db.add(Inventory(product_id=p.id,quantity=p.available_stock));items.append(product_dict(p))
        emit(db,'catalog.imported','Catalogue CSV imported',f'{len(items)} products validated and saved.',agent='merchant');return {'imported':len(items),'products':items}
    return mutate(db,request,{'sha':__import__('hashlib').sha256(raw).hexdigest()},run)

@router.post('/firewall/validate')
def firewall(body:FirewallProposal,request:Request,db=Depends(get_db)):
    # A sandbox validation tool. This route never creates an order or payment.
    return mutate(db,request,body.model_dump(exclude_none=True),lambda:validate_policy(db,body.model_dump(exclude_none=True)))

@router.get('/firewall/audit')
def firewall_audit(db=Depends(get_db)):
    return [p.payload for p in db.scalars(select(PolicyDecision).order_by(PolicyDecision.created_at.desc()).limit(100)).all()]

def csv_cell(value):
    """CSV quoting alone does not disable spreadsheet formulas."""
    if isinstance(value,str) and (value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r'))):
        return "'"+value
    return value


def csv_download(filename,headers,rows):
    output=io.StringIO(newline='')
    writer=csv.writer(output)
    writer.writerow(headers)
    for row in rows:writer.writerow([csv_cell(value) for value in row])
    return Response(output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{filename}"','X-Data-Source':'synthetic'})


@router.get('/transactions/template',dependencies=[Depends(merchant_role)])
def transaction_template(db=Depends(get_db)):
    from app.core.clock import business_day_start
    tokens=db.scalars(select(CustomerToken.customer_token).order_by(CustomerToken.customer_token).limit(3)).all()
    rows=[(token,125.50+i*25,'Grocery',(business_day_start()-timedelta(days=i+1)+timedelta(hours=10)).isoformat()) for i,token in enumerate(tokens)]
    return csv_download('pehchaan-transaction-template.csv',['customer_token','amount','category','created_at'],rows)


@router.get('/transactions/export',dependencies=[Depends(merchant_role)])
def transaction_export(db=Depends(get_db)):
    rows=db.scalars(select(Transaction).order_by(Transaction.created_at.desc())).all()
    return csv_download('pehchaan-transactions.csv',['id','customer_token','amount','category','created_at','campaign_id','simulated'],[(row.id,row.customer_token,money(row.amount),row.category,row.created_at.isoformat(),row.campaign_id or '',str(row.simulated).lower()) for row in rows])


@router.get('/transactions')
def transactions(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db=Depends(get_db)):
    total=db.scalar(select(func.count(Transaction.id)))
    rows=db.scalars(select(Transaction).order_by(Transaction.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return {'items':[{k:getattr(t,k) for k in ('id','customer_token','amount','category','campaign_id','simulated')}|{'created_at':t.created_at.isoformat()} for t in rows],'total':total,'page':page,'page_size':page_size}

@router.get('/events')
def events(limit:int=Query(30,ge=1,le=200),db=Depends(get_db)):return recent_events(db,limit)

@router.get('/events/stream')
async def stream_events(request:Request):
    try:cursor=int(request.headers.get('Last-Event-ID') or request.query_params.get('after','0'))
    except ValueError:raise HTTPException(422,'Invalid event cursor')
    async def stream():
        nonlocal cursor
        idle=0
        while not await request.is_disconnected():
            with SessionLocal() as db:
                maximum=db.scalar(select(func.max(AuditEvent.id))) or 0
                if maximum and cursor>maximum:cursor=0
                rows=db.scalars(select(AuditEvent).where(AuditEvent.id>cursor).order_by(AuditEvent.id).limit(100)).all()
                for row in rows:
                    cursor=row.id;yield f'id: {row.id}\ndata: {json.dumps(event_dict(row))}\n\n'
            if not rows:
                idle+=1
                if idle%15==0:yield ': heartbeat\n\n'
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

AGENTS=[('comeback','Comeback Agent'),('customer-intelligence','Customer Intelligence'),('voice','Voice Agent'),('buyer','Buyer Agent'),('seller-a','Merchant Agent A'),('seller-b','Merchant Agent B'),('seller-c','Merchant Agent C'),('supervisor','Negotiation Supervisor'),('firewall','Policy Firewall'),('payment','Payment Simulator'),('analytics','Analytics Agent')]
@router.get('/agents/status')
def agents_status(db=Depends(get_db)):
    events=recent_events(db,100);agents=[]
    sessions=db.scalars(select(NegotiationSession).where(NegotiationSession.status=='running')).all()
    runs=db.scalars(select(AgentRun).order_by(AgentRun.created_at.desc())).all()
    counts=dict(db.execute(select(AuditEvent.agent,func.count(AuditEvent.id)).group_by(AuditEvent.agent)).all())
    active=set()
    for session in sessions:
        node=session.payload.get('active_node','')
        if node=='collect_quotes':active.update(['seller-a','seller-b','seller-c','supervisor'])
        elif node in ('parse_requirement','dispatch_request','buyer_evaluation'):active.add('buyer')
        elif node=='firewall_validation':active.add('firewall')
        else:active.add('supervisor')
    for id,name in AGENTS:
        own=[e for e in events if e['agent']==id];last=own[0] if own else None
        agent_runs=[run for run in runs if run.payload.get('agent')==id]
        latest=agent_runs[0].payload if agent_runs else (last.get('data',{}) if last else {})
        status='running' if id in active else ('blocked' if last and last['status']=='blocked' else 'success' if last else 'idle')
        agents.append({'id':id,'name':name,'status':status,'current_task':last['title'] if last else 'Ready for a workflow','last_action':last['detail'] if last else 'No actions yet','duration_ms':latest.get('duration_ms',latest.get('elapsed_ms',0)),'tool_calls':sum(run.payload.get('tool_calls',0) for run in agent_runs) if agent_runs else counts.get(id,0)})
    return {'agents':agents,'events':events[:30]}

@router.get('/dashboard/summary')
def dashboard(days:int=Query(30,ge=7,le=90),db=Depends(get_db)):
    ref=datetime.now(timezone.utc);start=ref-timedelta(days=days);prev=start-timedelta(days=days)
    rows=db.scalars(select(Transaction)).all()
    def aware(t):return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    current=[t for t in rows if aware(t.created_at)>=start];previous=[t for t in rows if prev<=aware(t.created_at)<start]
    revenue=sum(t.amount for t in current);previous_revenue=sum(t.amount for t in previous)
    first={}
    for t in rows:
        dt=aware(t.created_at)
        if t.customer_token not in first or dt<first[t.customer_token]:first[t.customer_token]=dt
    returning=len({t.customer_token for t in current if first[t.customer_token]<start})
    revenue_by_date=defaultdict(lambda:{'revenue':0,'transactions':0})
    category=defaultdict(float)
    for t in current:
        d=aware(t.created_at).date().isoformat();revenue_by_date[d]['revenue']+=t.amount;revenue_by_date[d]['transactions']+=1;category[t.category]+=t.amount
    trend=[{'date':(start+timedelta(days=i+1)).date().isoformat(),'revenue':money(revenue_by_date[(start+timedelta(days=i+1)).date().isoformat()]['revenue']),'transactions':revenue_by_date[(start+timedelta(days=i+1)).date().isoformat()]['transactions']} for i in range(days)]
    retention=[]
    for i in range(8):
        end=ref-timedelta(weeks=7-i);begin=end-timedelta(weeks=1)
        active={t.customer_token for t in rows if begin<=aware(t.created_at)<end}
        retention.append({'week':begin.strftime('%d %b'),'returning':sum(first[token]<begin for token in active),'new':sum(first[token]>=begin for token in active)})
    cs=[campaign_dict(db,c) for c in db.scalars(select(Campaign).order_by(Campaign.created_at.desc())).all()]
    segs=segment_counts(db);at_risk_count=sum(s['count'] for s in segs if s['segment'] in ('At-Risk Customers','Declining Customers'))
    orders=db.scalars(select(BulkOrder)).all();security=db.scalars(select(PolicyDecision)).all()
    cohorts=weekly_cohorts(rows,ref)
    merchant=db.get(Merchant,'sharma-kirana')
    return {'merchant':{'id':merchant.id,'name':merchant.name,'location':merchant.location,'category':merchant.category},'period_days':days,'metrics':{'revenue':money(revenue),'previous_revenue':money(previous_revenue),'revenue_change':round((revenue-previous_revenue)/previous_revenue*100,1) if previous_revenue else 0,'returning_customers':returning,'at_risk_customers':at_risk_count,'average_basket':money(revenue/len(current)) if current else 0,'transactions':len(current),'bulk_orders':len(orders),'campaign_redemptions':sum(c['stats']['redeemed'] for c in cs),'discount_expense':money(sum(c['stats']['discount_expense'] for c in cs)),'incremental_gross_profit':money(sum(c['stats']['incremental_gross_profit'] for c in cs if not c['stats']['preliminary'])),'active_agents':sum(a['status']=='running' for a in agents_status(db)['agents'])},'revenue_trend':trend,'retention_trend':retention,'segments':segs,'category_revenue':[{'category':k,'revenue':money(v)} for k,v in sorted(category.items(),key=lambda x:-x[1])],'cohorts':cohorts,'campaigns':cs,'recent_events':recent_events(db,12),'recommendation':{'title':f'{at_risk_count} regulars deserve a reason to return','description':f'{at_risk_count} customers show delayed visits or a decline in purchases at your store. Propose ₹15 off a ₹250 bill; merchant approval required.','offer_amount':15,'minimum_bill':250,'eligible_customers':at_risk_count,'projected_gross_profit':money(at_risk_count*.35*(250*.22-15)),'projection':True},'provider':{'mode':'live' if settings.sarvam_api_key else 'demo','configured':bool(settings.sarvam_api_key)},'security':{'blocked':sum(p.status=='BLOCKED' for p in security),'eligible':sum(p.status!='BLOCKED' for p in security)},'bulk_performance':[{'month':(ref-timedelta(days=30*i)).strftime('%b'),'orders':sum(aware(o.created_at).strftime('%Y-%m')==(ref-timedelta(days=30*i)).strftime('%Y-%m') for o in orders),'total':money(sum(o.payload.get('total_amount',0) for o in orders if aware(o.created_at).strftime('%Y-%m')==(ref-timedelta(days=30*i)).strftime('%Y-%m')))} for i in reversed(range(3))]}

@router.post('/demo/reset',dependencies=[Depends(merchant_role)])
async def reset_demo(request:Request,db=Depends(get_db)):
    from app.database.seed import seed_demo
    from app.services.negotiation import TASKS
    tasks=[task for task in TASKS.values() if not task.done()]
    for task in tasks:task.cancel()
    if tasks:await asyncio.gather(*tasks,return_exceptions=True)
    def run():
        result=seed_demo(db,reset=True)
        from app.services.retail import seed_retail_demo
        seed_retail_demo(db);return result|{'transactions':db.scalar(select(func.count(Transaction.id)))}
    return mutate(db,request,{},run)

@router.get('/settings/integrations')
def integrations(db=Depends(get_db)):
    return health(db)|{'merchant_language':db.get(Merchant,'sharma-kirana').language,'authentication':'local_demo_roles','documents':'sarvam_adapter_with_reviewed_demo_fallback','paytm_enabled':False}

@router.patch('/settings/merchant',dependencies=[Depends(merchant_role)])
async def settings_update(request:Request,db=Depends(get_db)):
    data=await request.json();language=data.get('language')
    if language not in ('hi-IN','mr-IN','en-IN'):raise HTTPException(422,'Choose Hindi, Marathi or English')
    def run():
        merchant=db.get(Merchant,'sharma-kirana');merchant.language=language;emit(db,'settings.updated','Merchant language updated',language,agent='merchant');return {'language':language}
    return mutate(db,request,data,run)

@router.post('/transactions/import',dependencies=[Depends(merchant_role)])
async def transaction_import(request:Request,file:UploadFile=File(...),db=Depends(get_db)):
    """Import only known pseudonymous demo tokens; never infer external merchant activity."""
    import hashlib,math,re
    if not file.filename or not file.filename.lower().endswith('.csv'):raise HTTPException(422,'Upload a transaction CSV file')
    raw=await file.read(settings.max_upload_bytes+1)
    if len(raw)>settings.max_upload_bytes:raise HTTPException(413,'File exceeds 10 MB upload limit')
    digest=hashlib.sha256(raw).hexdigest()
    try:
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        if not 1<=len(rows)<=5000:raise ValueError('CSV must contain between 1 and 5000 rows')
        valid=[]
        for index,row in enumerate(rows):
            token=row.get('customer_token','')
            if not re.fullmatch(r'PK-\d{4}',token) or not db.get(CustomerToken,token):raise ValueError(f'Row {index+1}: use a known pseudonymous customer token')
            amount=float(row.get('amount','0'))
            if not math.isfinite(amount) or not 0<amount<=1000000:raise ValueError(f'Row {index+1}: invalid purchase amount')
            timestamp=datetime.fromisoformat(row['created_at'].replace('Z','+00:00'))
            if timestamp.tzinfo is None:timestamp=timestamp.replace(tzinfo=timezone.utc)
            if timestamp>now()+timedelta(minutes=5):raise ValueError(f'Row {index+1}: transaction date is in the future')
            valid.append({'customer_token':token,'amount':money(amount),'category':str(row.get('category','Grocery'))[:60],'created_at':timestamp})
    except (UnicodeDecodeError,ValueError,KeyError) as error:raise HTTPException(422,f'Invalid transaction CSV: {str(error)[:500]}')
    def run():
        for row in valid:db.add(Transaction(merchant_id='sharma-kirana',**row,gross_profit=money(row['amount']*.22),simulated=True))
        db.flush();refresh_metrics(db);emit(db,'transactions.imported','Synthetic transaction CSV imported',f'{len(valid)} records validated. Customer segments recalculated.',agent='analytics');return {'imported':len(valid),'simulated':True}
    # Content-level deduplication survives clients that generate a new request
    # key for each click. Retain ordinary caller-key conflict detection as well.
    if db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(:lock)'),{'lock':int.from_bytes(bytes.fromhex(digest)[:8],signed=True)})
    once=lambda:execute_once(db,'file-'+digest,request.url.path,{'digest':digest},run)
    result=execute_once(db,request.headers.get('Idempotency-Key'),request.url.path,{'digest':digest},once)
    db.commit();return result
