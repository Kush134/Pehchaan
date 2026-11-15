from __future__ import annotations

import asyncio
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave
from datetime import datetime,timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select

from app.core.config import settings
from app.database.session import get_db, SessionLocal
from app.models import NegotiationSession, BulkOrder, AuditEvent
from app.services import negotiation, payments, voice
from app.services.requirement_parser import ParseRequirementRequest,parse_requirement
from app.services.events import emit,event_dict
from app.integrations.sarvam import SarvamProvider, DocumentIntelligenceProvider
from app.services.idempotency import execute_once

router=APIRouter()

def merchant_role(request:Request):
    # Local demo role separation, deliberately not advertised as production auth.
    if request.headers.get('X-Demo-Role','merchant')!='merchant':
        raise HTTPException(403,'This operation requires the merchant demo role.')

class Approval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    merchant_approved:bool=False
    buyer_confirmed:bool=False

class DeliveryConfirmation(BaseModel):
    confirmed:bool=False

class VoiceApproval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    session_id:str
    proposal_id:str
    approved:bool

class Synthesis(BaseModel):
    text:str=Field(min_length=1,max_length=2500)
    language:voice.Language='hi-IN'


async def upload_bytes(file:UploadFile) -> bytes:
    content=await file.read(settings.max_upload_bytes+1)
    if len(content)>settings.max_upload_bytes: raise HTTPException(413,'File exceeds the 10 MB upload limit.')
    if not content: raise HTTPException(422,'The uploaded file is empty.')
    return content


def validate_document(content:bytes,content_type:str):
    if content_type=='application/pdf':
        if not content.startswith(b'%PDF-'): raise HTTPException(422,'The file is not a valid PDF document.')
        return
    if content_type not in {'image/jpeg','image/png','image/webp'}:
        raise HTTPException(415,'Upload a JPEG, PNG, WebP image or PDF document.')
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width*image.height>25_000_000: raise HTTPException(422,'Image exceeds the 25 megapixel limit.')
            if image.format not in {'JPEG','PNG','WEBP'}: raise HTTPException(415,'Unsupported image encoding.')
            image.verify()
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError):
        raise HTTPException(422,'The image could not be decoded. Upload a valid image.')


def audio_duration(content:bytes,suffix:str):
    path=None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix,delete=False) as tmp:
            tmp.write(content);path=tmp.name
        if shutil.which('ffprobe'):
            result=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',path],capture_output=True,text=True,timeout=8,check=True)
            payload=json.loads(result.stdout)
            duration=float(payload.get('format',{}).get('duration',0))
            # Browser WebM sometimes has no duration metadata: decode and count samples.
            if not duration:
                decoded=subprocess.run(['ffmpeg','-v','error','-i',path,'-f','s16le','-ar','16000','-ac','1','-t','31','-'],capture_output=True,timeout=10,check=True)
                duration=len(decoded.stdout)/32000
        else:
            decoder=shutil.which('ffmpeg')
            if not decoder:
                try:
                    import imageio_ffmpeg
                    decoder=imageio_ffmpeg.get_ffmpeg_exe()
                except ImportError:
                    decoder=None
            if decoder:
                decoded=subprocess.run([decoder,'-v','error','-i',path,'-f','s16le','-ar','16000','-ac','1','-t','31','-'],capture_output=True,timeout=10,check=True)
                duration=len(decoded.stdout)/32000
            else:
                try:
                    with wave.open(io.BytesIO(content)) as audio: duration=audio.getnframes()/audio.getframerate()
                except (wave.Error,EOFError):
                    raise HTTPException(503,'Server audio validator unavailable. Install ffmpeg or use a WAV file; text commands remain available.')
        if duration<=0: raise HTTPException(422,'Audio is empty or its duration could not be verified.')
        if duration>30: raise HTTPException(422,'Saaras synchronous audio must be 30 seconds or shorter. Please record a shorter command.')
        return duration
    except (subprocess.SubprocessError,json.JSONDecodeError,ValueError):
        raise HTTPException(422,'The audio file could not be decoded. Upload a valid recording under 30 seconds.')
    finally:
        if path and os.path.exists(path): os.unlink(path)


@router.post('/haggle/parse-requirement')
async def parse_buyer_requirement(data:ParseRequirementRequest,db=Depends(get_db)):
    result=await parse_requirement(data)
    emit(db,'buyer.requirement_parsed','Buyer requirement ready for review',f"{len(result['items'])} product lines; provider: {result['provider']}. No negotiation or order was started.",agent='buyer',data={'provider':result['provider'],'items':len(result['items']),'review_required':True})
    db.commit()
    return result


@router.get('/haggle/catalogue')
def seller_catalogue(db=Depends(get_db)):
    return {'products':[{'id':key,**value} for key,value in negotiation.PRODUCTS.items()],
        'sellers':[{**seller,'available_stock':negotiation.seller_stock(db,seller['id'])} for seller in negotiation.SELLERS],
        'default_items':negotiation.DEFAULT_ITEMS,'simulated':True}


@router.get('/haggle/sessions')
def sessions(db=Depends(get_db)):
    return {'items':[negotiation.serialize(row) for row in db.scalars(select(NegotiationSession).order_by(NegotiationSession.created_at.desc()).limit(50))]}


@router.post('/haggle/sessions')
def create_session(data:negotiation.BuyerRequirement,request:Request,db=Depends(get_db)):
    result=execute_once(db,request.headers.get('Idempotency-Key'),request.url.path,data.model_dump(mode='json'),lambda:negotiation.create_session(db,data))
    db.commit()
    return result


@router.get('/haggle/sessions/{sid}')
def session(sid:str,db=Depends(get_db)):
    return negotiation.serialize(negotiation.load_session(db,sid))


@router.post('/haggle/sessions/{sid}/start')
async def start(sid:str,db=Depends(get_db)):
    row=negotiation.load_session(db,sid)
    if row.status=='running': return negotiation.serialize(row)
    if row.status!='created': raise HTTPException(409,'Only a new session can be started. Create a new session or resume a paused one.')
    row.status='running';db.commit();negotiation.launch(sid)
    return negotiation.serialize(row)


@router.post('/haggle/sessions/{sid}/pause')
def pause(sid:str,db=Depends(get_db)):
    row=negotiation.load_session(db,sid)
    if row.status=='paused': return negotiation.serialize(row)
    if row.status!='running': raise HTTPException(409,'Only a running negotiation can be paused.')
    row.status='paused';emit(db,'negotiation.paused','Negotiation paused','In-flight provider requests may finish; the next agent stage waits for resume.',agent='supervisor',data={'session_id':sid});db.commit()
    return negotiation.serialize(row)


@router.post('/haggle/sessions/{sid}/resume')
async def resume(sid:str,db=Depends(get_db)):
    row=negotiation.load_session(db,sid)
    if row.status not in {'paused','running'}: raise HTTPException(409,'Only a paused or interrupted running negotiation can be resumed.')
    row.status='running';emit(db,'negotiation.resumed','Negotiation resumed',agent='supervisor',data={'session_id':sid});db.commit();negotiation.launch(sid)
    return negotiation.serialize(row)


@router.post('/haggle/sessions/{sid}/cancel')
def cancel(sid:str,db=Depends(get_db)):
    row=negotiation.load_session(db,sid)
    if row.status=='cancelled': return negotiation.serialize(row)
    if row.status=='confirmed': raise HTTPException(409,'An already confirmed order must be managed in the ledger.')
    row.status='cancelled';emit(db,'negotiation.cancelled','Negotiation cancelled','No new order or payment will be created.',agent='supervisor',data={'session_id':sid});db.commit()
    task=negotiation.TASKS.get(sid)
    if task: task.cancel()
    return negotiation.serialize(row)


@router.post('/haggle/sessions/{sid}/reset')
def reset(sid:str,request:Request,db=Depends(get_db)):
    old=negotiation.load_session(db,sid)
    if old.status=='running': raise HTTPException(409,'Cancel the active negotiation before resetting it.')
    result=execute_once(db,request.headers.get('Idempotency-Key'),request.url.path,{},lambda:negotiation.create_session(db,negotiation.BuyerRequirement(requirement=old.payload['requirement'],budget=old.payload['budget'],items=old.payload['items'])))
    db.commit()
    return result


@router.get('/haggle/sessions/{sid}/events')
async def session_events(sid:str,request:Request,after:int=0,last_event_id:str|None=Header(default=None)):
    try: cursor=max(after,int(last_event_id or 0))
    except ValueError: raise HTTPException(422,'Last-Event-ID must be a numeric event identifier.')
    async def stream():
        nonlocal cursor
        yield 'retry: 2000\n\n'
        while not await request.is_disconnected():
            with SessionLocal() as db:
                rows=db.scalars(select(AuditEvent).where(AuditEvent.id>cursor).order_by(AuditEvent.id).limit(100)).all()
                for row in rows:
                    cursor=row.id
                    if row.data.get('session_id')==sid:
                        yield f'id: {row.id}\ndata: {json.dumps(event_dict(row),ensure_ascii=False)}\n\n'
            yield ': heartbeat\n\n'
            await asyncio.sleep(.7)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})


@router.post('/haggle/sessions/{sid}/confirm')
def confirm(sid:str,data:Approval,db=Depends(get_db)):
    return payments.confirm_session(db,sid,merchant_approved=data.merchant_approved,buyer_confirmed=data.buyer_confirmed)


@router.get('/orders')
def orders(db=Depends(get_db)):
    return {'items':[payments.order_dict(order) for order in db.scalars(select(BulkOrder).order_by(BulkOrder.created_at.desc()).limit(100))]}


@router.get('/orders/{oid}')
def order(oid:str,db=Depends(get_db)):
    return payments.order_dict(payments.load_order(db,oid))


@router.post('/orders/{oid}/packed',dependencies=[Depends(merchant_role)])
def packed(oid:str,db=Depends(get_db)): return payments.transition(db,oid,'packed')

@router.post('/orders/{oid}/delivery-confirm')
def delivered(oid:str,data:DeliveryConfirmation,db=Depends(get_db)): return payments.transition(db,oid,'delivery-confirm',data.confirmed)

@router.post('/orders/{oid}/release',dependencies=[Depends(merchant_role)])
def release(oid:str,db=Depends(get_db)): return payments.transition(db,oid,'release')

@router.post('/orders/{oid}/void',dependencies=[Depends(merchant_role)])
def void(oid:str,db=Depends(get_db)): return payments.transition(db,oid,'void')


@router.post('/orders/{oid}/inspection',dependencies=[Depends(merchant_role)])
async def inspection(oid:str,file:UploadFile=File(...),db=Depends(get_db)):
    order=payments.load_order(db,oid)
    content=await upload_bytes(file);validate_document(content,file.content_type or '')
    if not (file.content_type or '').startswith('image/'): raise HTTPException(415,'Packing inspection needs a photograph.')
    with Image.open(io.BytesIO(content)) as image:
        width,height=image.size
    # Deliberately modest local advisory; never claim automated product verification.
    advisory={'advisory':True,'provider':'local-review','result':f'Packing photo received ({width} × {height}). Image is decodable; contents, quantities and delivery have not been verified.',
        'human_confirmation_required':True,'created_at':datetime.now(timezone.utc).isoformat(),
        'filename':Path(file.filename or 'packing-photo').name[:120]}
    order.payload={**order.payload,'inspection':advisory}
    emit(db,'order.inspection','Packing photo ready for human review',advisory['result'],agent='payment',data={'order_id':oid});db.commit()
    return advisory


@router.post('/payments/simulate')
def simulate_payment(data:dict):
    raise HTTPException(409,'Use a confirmed Haggle order. Payment simulation is created atomically after both required approvals; arbitrary payment requests are disabled.')


@router.post('/voice/chat',dependencies=[Depends(merchant_role)])
async def voice_chat(data:voice.VoiceChat,db=Depends(get_db)):
    try: return await voice.chat(db,data)
    except ValueError as exc: raise HTTPException(422,str(exc))


@router.post('/voice/approve',dependencies=[Depends(merchant_role)])
async def voice_approval(data:VoiceApproval,db=Depends(get_db)):
    try: return voice.approve(db,data.session_id,data.proposal_id,data.approved)
    except ValueError as exc: raise HTTPException(422,str(exc))


@router.get('/voice/history')
def history(session_id:str,db=Depends(get_db)):
    row=voice.safe_session(db,session_id)
    return {'session_id':row.id,'messages':row.payload.get('messages',[]),'proposal':row.payload.get('proposal'),'language':row.payload.get('language','hi-IN'),'status':row.status}


@router.post('/voice/transcribe')
async def transcribe(file:UploadFile=File(...),language:voice.Language=Form('hi-IN'),duration_seconds:float=Form(default=0),db=Depends(get_db)):
    if duration_seconds>30: raise HTTPException(422,'Record at most 30 seconds for synchronous speech recognition.')
    content=await upload_bytes(file)
    ctype=(file.content_type or '').split(';')[0]
    if ctype not in {'audio/wav','audio/x-wav','audio/webm','video/webm','audio/ogg','audio/mpeg','audio/mp4','audio/aac','audio/flac'}:
        raise HTTPException(415,'Unsupported audio format. Use WAV, WebM, OGG, MP3, M4A or FLAC.')
    suffix=Path(file.filename or 'recording.webm').suffix.lower()
    if suffix not in {'.wav','.webm','.ogg','.mp3','.m4a','.mp4','.aac','.flac'}: suffix='.webm'
    measured=await asyncio.to_thread(audio_duration,content,suffix)
    result=await SarvamProvider().transcribe(content,'recording'+suffix,ctype,language)
    emit(db,'voice.transcribed','Audio transcription completed' if result['transcript'] else 'Speech provider unavailable',
        f"Provider: {result['provider']}. Verified duration {measured:.1f}s.",agent='voice',data={'provider':result['provider'],'duration_seconds':round(measured,2)});db.commit()
    return {**result,'duration_seconds':round(measured,2)}


@router.post('/voice/synthesize')
async def synthesize(data:Synthesis): return await SarvamProvider().synthesize(data.text,data.language)


@router.post('/documents/extract')
async def extract(file:UploadFile=File(...),language:voice.Language=Form('hi-IN'),db=Depends(get_db)):
    content=await upload_bytes(file);ctype=file.content_type or '';validate_document(content,ctype)
    suffix='.pdf' if ctype=='application/pdf' else '.png' if ctype=='image/png' else '.webp' if ctype=='image/webp' else '.jpg'
    result=await DocumentIntelligenceProvider().extract(content,'document'+suffix,ctype,language)
    emit(db,'document.extracted','Document extraction ready for review',f"Provider: {result['provider']}. Entries require human review before saving.",agent='voice',data={'provider':result['provider'],'items':len(result['items'])});db.commit()
    return result
