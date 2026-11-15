import hashlib,json
from fastapi import HTTPException
from app.models import IdempotencyRecord

def execute_once(db,key,path,payload,operation):
    if not key: return operation()
    if len(key)>150: raise HTTPException(422,'Idempotency key is too long')
    scoped=hashlib.sha256(f'{path}:{key}'.encode()).hexdigest()
    fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
    previous=db.get(IdempotencyRecord,scoped)
    if previous:
        if previous.fingerprint!=fingerprint: raise HTTPException(409,'Idempotency key was already used for a different request')
        return previous.response
    response=operation()
    db.add(IdempotencyRecord(key=scoped,fingerprint=fingerprint,response=response));db.flush()
    return response
