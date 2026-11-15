from datetime import datetime
from sqlalchemy import String,Boolean,DateTime,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from app.models import now
from app.database.session import Base

class SmsNotification(Base):
    __tablename__='sms_notifications'
    id:Mapped[str]=mapped_column(ForeignKey('telephony_calls.id'),primary_key=True)
    campaign_id:Mapped[str]=mapped_column(ForeignKey('campaigns.id'),index=True)
    status:Mapped[str]=mapped_column(String,default='queued')
    body:Mapped[str]=mapped_column(String)
    provider_sid:Mapped[str|None]=mapped_column(String,nullable=True,unique=True)
    simulated:Mapped[bool]=mapped_column(Boolean,default=False)
    error:Mapped[str|None]=mapped_column(String,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
