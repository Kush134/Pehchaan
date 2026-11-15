import json
import logging
from sqlalchemy import select
from app.core.config import settings
from app.models import AuditEvent

logger=logging.getLogger('pehchaan.events')
_redis=None
_redis_available=False
if settings.redis_url:
    try:
        from redis import Redis
        _redis=Redis.from_url(settings.redis_url,socket_connect_timeout=.5,socket_timeout=.5)
        _redis.ping(); _redis_available=True
    except Exception:
        logger.warning('Redis unavailable; persistent database event stream enabled')

def event_dict(event):
    return {'id':event.id,'type':event.type,'title':event.title,'detail':event.detail,'agent':event.agent,'status':event.status,'data':event.data,'created_at':event.created_at.isoformat()}

def emit(db, type, title, detail='', agent='system', data=None, status='success'):
    global _redis_available
    event=AuditEvent(type=type,title=title,detail=detail,agent=agent,data=data or {},status=status)
    db.add(event); db.flush()
    if _redis_available:
        try: _redis.publish('pehchaan:events',json.dumps(event_dict(event)))
        except Exception:
            _redis_available=False
            logger.warning('Redis publish failed; event persisted in database')
    return event_dict(event)

def recent_events(db, limit=30):
    return [event_dict(x) for x in db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)).all()]

def redis_status():
    global _redis_available
    if _redis is not None:
        try:_redis_available=bool(_redis.ping())
        except Exception:_redis_available=False
    return 'connected' if _redis_available else 'database_polling_fallback'
