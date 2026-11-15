import logging,time,uuid
from collections import defaultdict,deque
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.config import settings
from app.database.session import SessionLocal
from app.database.seed import seed_demo
from app.api.core import router as core_router
from app.api.workflows import router as workflow_router
from app.api.checkout import router as checkout_router
from app.api.telephony import router as telephony_router
from app.api.retail import router as retail_router
from app.api.finance import router as finance_router
from app.api.business_analytics import router as business_router
from app.api.sms import router as sms_router,public_router as sms_public_router

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger('pehchaan.api')

@asynccontextmanager
async def lifespan(app):
    if settings.auto_seed:
        with SessionLocal() as db:
            seed_demo(db)
            from app.services.retail import seed_retail_demo
            seed_retail_demo(db);db.commit()
    yield

app=FastAPI(title='Pehchaan Merchant Growth OS',version='1.0.0',lifespan=lifespan,description='Synthetic merchant demonstration. All financial transactions are simulated.')
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins.split(','),allow_credentials=False,allow_methods=['GET','POST','PATCH','DELETE','OPTIONS'],allow_headers=['Content-Type','Idempotency-Key','Last-Event-ID','X-Demo-Role','X-Request-ID'],expose_headers=['X-Request-ID'])
_requests=defaultdict(deque)

@app.middleware('http')
async def guard_request(request:Request,call_next):
    request_id=str(uuid.uuid4());request.state.request_id=request_id
    try:length=int(request.headers.get('content-length','0'))
    except ValueError:return JSONResponse({'detail':'Invalid Content-Length'},status_code=400)
    if length>settings.max_upload_bytes+65536:return JSONResponse({'detail':'Request exceeds upload limit','request_id':request_id},status_code=413)
    expensive=request.method=='POST' and any(x in request.url.path for x in ('/voice/','/documents/','/start','/parse-requirement'))
    if expensive:
        key=(request.client.host if request.client else 'local',request.url.path);bucket=_requests[key];clock=time.monotonic()
        while bucket and bucket[0]<clock-60:bucket.popleft()
        if len(bucket)>=30:return JSONResponse({'detail':'AI request limit reached. Try again in a minute.','request_id':request_id},status_code=429,headers={'Retry-After':'60'})
        bucket.append(clock)
    started=time.monotonic()
    try:response=await call_next(request)
    except Exception:
        logger.exception('Request failed id=%s method=%s path=%s',request_id,request.method,request.url.path)
        return JSONResponse({'detail':'Unexpected server error. Please retry or inspect the server logs using the request ID.','request_id':request_id},status_code=500)
    response.headers['X-Request-ID']=request_id
    logger.info('request id=%s method=%s path=%s status=%s duration_ms=%d',request_id,request.method,request.url.path,response.status_code,(time.monotonic()-started)*1000)
    return response

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    issues=['.'.join(str(p) for p in e['loc'][1:])+': '+e['msg'] for e in exc.errors()]
    return JSONResponse({'detail':'; '.join(issues),'request_id':getattr(request.state,'request_id','')},status_code=422)

app.include_router(core_router,prefix='/api/v1')
app.include_router(workflow_router,prefix='/api/v1')
app.include_router(checkout_router,prefix='/api/v1')
app.include_router(telephony_router,prefix='/api/v1')
app.include_router(retail_router,prefix='/api/v1')
app.include_router(finance_router,prefix='/api/v1')
app.include_router(business_router,prefix='/api/v1')
app.include_router(sms_router,prefix='/api/v1')
app.include_router(sms_public_router)
@app.get('/')
def root():return {'name':'Pehchaan','docs':'/docs','health':'/api/v1/health','payment_provider':'simulated'}
