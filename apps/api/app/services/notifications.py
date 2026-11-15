"""Default channel selection shared by campaigns and reviewed voice actions."""
from app.core.config import settings
from app.services import telephony,sms
from app.models.sms import SmsNotification
from app.database.session import SessionLocal

def queue_campaign_call(db,campaign_id,simulate=False):
    return sms.queue(db,campaign_id,simulate) if settings.notification_channel=='sms' else telephony.queue_campaign_call(db,campaign_id,simulate)

def dispatch_call(db,id):
    return sms.dispatch(db,id) if db.get(SmsNotification,id) else telephony.dispatch_call(db,id)

def call_dict(row):
    # Pending proposal serialization must not commit or expose credentials.
    if getattr(row,'provider','') in {'twilio-sms','sms-simulation'}:
        from sqlalchemy.orm import object_session
        db=object_session(row)
        return sms.serialize(db,db.get(SmsNotification,row.id))
    return telephony.call_dict(row)
