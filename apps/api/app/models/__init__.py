from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database.session import Base

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)

class Merchant(Base):
    __tablename__='merchants'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    name: Mapped[str]=mapped_column(String)
    location: Mapped[str]=mapped_column(String)
    category: Mapped[str]=mapped_column(String,default='Kirana / Grocery')
    language: Mapped[str]=mapped_column(String,default='hi-IN')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class CustomerToken(Base):
    __tablename__='customer_tokens'
    customer_token: Mapped[str]=mapped_column(String,primary_key=True)
    merchant_id: Mapped[str]=mapped_column(ForeignKey('merchants.id'),index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class Transaction(Base):
    __tablename__='transactions'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    merchant_id: Mapped[str]=mapped_column(ForeignKey('merchants.id'),index=True)
    customer_token: Mapped[str]=mapped_column(ForeignKey('customer_tokens.customer_token'),index=True)
    amount: Mapped[float]=mapped_column(Float)
    gross_profit: Mapped[float]=mapped_column(Float,default=0)
    category: Mapped[str]=mapped_column(String,default='Grocery')
    campaign_id: Mapped[str|None]=mapped_column(String,nullable=True,index=True)
    simulated: Mapped[bool]=mapped_column(Boolean,default=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)

class CustomerMetric(Base):
    __tablename__='customer_metrics'
    customer_token: Mapped[str]=mapped_column(ForeignKey('customer_tokens.customer_token'),primary_key=True)
    merchant_id: Mapped[str]=mapped_column(ForeignKey('merchants.id'),index=True)
    customer_segment: Mapped[str]=mapped_column(String,index=True)
    risk_score: Mapped[float]=mapped_column(Float)
    payload: Mapped[dict]=mapped_column(JSON)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)

class Product(Base):
    __tablename__='products'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    merchant_id: Mapped[str]=mapped_column(ForeignKey('merchants.id'),index=True)
    name: Mapped[str]=mapped_column(String)
    category: Mapped[str]=mapped_column(String)
    unit: Mapped[str]=mapped_column(String)
    selling_price: Mapped[float]=mapped_column(Float)
    available_stock: Mapped[int]=mapped_column(Integer)
    purchase_price: Mapped[float]=mapped_column(Float)
    minimum_selling_price: Mapped[float]=mapped_column(Float)
    supplier: Mapped[str]=mapped_column(String,default='Local supplier')
    sku: Mapped[str]=mapped_column(String,default='')
    barcode: Mapped[str]=mapped_column(String,default='')
    variant: Mapped[str]=mapped_column(String,default='Standard')
    reorder_point: Mapped[int]=mapped_column(Integer,default=20)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)

class Inventory(Base):
    __tablename__='inventory'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    product_id: Mapped[str]=mapped_column(ForeignKey('products.id'),unique=True)
    quantity: Mapped[int]=mapped_column(Integer)

class Campaign(Base):
    __tablename__='campaigns'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    merchant_id: Mapped[str]=mapped_column(ForeignKey('merchants.id'),index=True)
    name: Mapped[str]=mapped_column(String)
    target_segment: Mapped[str]=mapped_column(String)
    offer_amount: Mapped[float]=mapped_column(Float)
    minimum_bill: Mapped[float]=mapped_column(Float)
    start_date: Mapped[str]=mapped_column(String)
    end_date: Mapped[str]=mapped_column(String)
    budget: Mapped[float]=mapped_column(Float)
    max_customers: Mapped[int]=mapped_column(Integer)
    language: Mapped[str]=mapped_column(String)
    ab_test: Mapped[bool]=mapped_column(Boolean,default=True)
    status: Mapped[str]=mapped_column(String,default='draft')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class CampaignVariant(Base):
    __tablename__='campaign_variants'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    campaign_id: Mapped[str]=mapped_column(ForeignKey('campaigns.id'),index=True)
    name: Mapped[str]=mapped_column(String)
    offer_amount: Mapped[float]=mapped_column(Float)
    minimum_bill: Mapped[float]=mapped_column(Float)

class CampaignAssignment(Base):
    __tablename__='campaign_assignments'
    __table_args__=(UniqueConstraint('campaign_id','customer_token'),)
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    campaign_id: Mapped[str]=mapped_column(ForeignKey('campaigns.id'),index=True)
    customer_token: Mapped[str]=mapped_column(ForeignKey('customer_tokens.customer_token'))
    variant: Mapped[str]=mapped_column(String)
    redeemed: Mapped[bool]=mapped_column(Boolean,default=False)

class Redemption(Base):
    __tablename__='redemptions'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    assignment_id: Mapped[str]=mapped_column(ForeignKey('campaign_assignments.id'),unique=True)
    campaign_id: Mapped[str]=mapped_column(ForeignKey('campaigns.id'),index=True)
    discount: Mapped[float]=mapped_column(Float)
    amount: Mapped[float]=mapped_column(Float)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class PolicyMandate(Base):
    __tablename__='policy_mandates'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    payload: Mapped[dict]=mapped_column(JSON)
    signature: Mapped[str]=mapped_column(String)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class PolicyDecision(Base):
    __tablename__='policy_decisions'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    status: Mapped[str]=mapped_column(String,index=True)
    payload: Mapped[dict]=mapped_column(JSON)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ReplayNonce(Base):
    __tablename__='replay_nonces'
    nonce: Mapped[str]=mapped_column(String,primary_key=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class IdempotencyRecord(Base):
    __tablename__='idempotency_records'
    key: Mapped[str]=mapped_column(String,primary_key=True)
    fingerprint: Mapped[str]=mapped_column(String)
    response: Mapped[dict]=mapped_column(JSON)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class AuditEvent(Base):
    __tablename__='audit_events'
    id: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    type: Mapped[str]=mapped_column(String,index=True)
    title: Mapped[str]=mapped_column(String)
    detail: Mapped[str]=mapped_column(String,default='')
    agent: Mapped[str]=mapped_column(String,default='system')
    status: Mapped[str]=mapped_column(String,default='success')
    data: Mapped[dict]=mapped_column(JSON,default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)

class WorkflowMixin:
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    status: Mapped[str]=mapped_column(String,default='pending')
    payload: Mapped[dict]=mapped_column(JSON,default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)

class Buyer(WorkflowMixin,Base): __tablename__='buyers'
class Seller(WorkflowMixin,Base): __tablename__='sellers'
class BulkOrder(WorkflowMixin,Base): __tablename__='bulk_orders'
class BulkOrderItem(WorkflowMixin,Base): __tablename__='bulk_order_items'
class SellerQuote(WorkflowMixin,Base): __tablename__='seller_quotes'
class NegotiationSession(WorkflowMixin,Base): __tablename__='negotiation_sessions'
class AgentRun(WorkflowMixin,Base): __tablename__='agent_runs'
class PaymentSimulation(WorkflowMixin,Base): __tablename__='payment_simulations'
class VoiceSession(WorkflowMixin,Base): __tablename__='voice_sessions'

class TelephonyCall(Base):
    __tablename__ = 'telephony_calls'
    __table_args__ = (UniqueConstraint('campaign_id', 'customer_token'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey('campaigns.id'), index=True)
    customer_token: Mapped[str] = mapped_column(ForeignKey('customer_tokens.customer_token'), index=True)
    customer_name: Mapped[str] = mapped_column(String)
    phone: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='queued', index=True)
    provider: Mapped[str] = mapped_column(String, default='sarvam')
    provider_attempt_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    offer_amount: Mapped[float] = mapped_column(Float)
    minimum_bill: Mapped[float] = mapped_column(Float)
    script: Mapped[str] = mapped_column(String)
    audio_base64: Mapped[str | None] = mapped_column(String, nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    acceptance_source: Mapped[str | None] = mapped_column(String, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed: Mapped[bool] = mapped_column(Boolean, default=False)
    checkout_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

from app.models.checkout import RetailCheckout  # noqa: E402,F401

from app.models.retail import StockBatch,RetailSale,RetailSaleLine,StockMovement,SupplierReorder  # noqa: E402,F401
from app.models.finance import Expense,KhataPayment  # noqa: E402,F401
from app.models.sms import SmsNotification  # noqa: E402,F401
