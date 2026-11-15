"""Public callback surface for a local telephony development tunnel.

The merchant API stays on port 8000. This independent ASGI app exposes only
provider-authenticated callbacks and capability-protected announcement audio.
"""
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.telephony import router as telephony_router
from app.api.sms import public_router as sms_public_router

CALLBACK_PATHS = frozenset({
    '/telephony/audio/{call_id}',
    '/telephony/webhooks/twilio-digits/{call_id}',
    '/telephony/webhooks/twilio-status/{call_id}',
    '/telephony/webhooks/sarvam/{call_id}',
})

app = FastAPI(title='Pehchaan phone callbacks', docs_url=None, redoc_url=None, openapi_url=None)
callbacks = APIRouter()
# Reuse the authenticated handlers and dependencies, without importing merchant
# routes into the public app. This list is explicit so new API routes stay private.
callbacks.routes.extend(route for route in telephony_router.routes if getattr(route, 'path', None) in CALLBACK_PATHS)
app.include_router(callbacks, prefix='/api/v1')
app.include_router(sms_public_router)


@app.middleware('http')
async def callback_request_limit(request: Request, call_next):
    if request.method == 'POST':
        try:
            length = int(request.headers.get('content-length', '-1'))
        except ValueError:
            return JSONResponse({'detail': 'Invalid Content-Length'}, status_code=400)
        if length < 0:
            return JSONResponse({'detail': 'Content-Length is required'}, status_code=411)
        if length > 65536:
            return JSONResponse({'detail': 'Callback exceeds size limit'}, status_code=413)
    return await call_next(request)


@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'telephony-callbacks'}
