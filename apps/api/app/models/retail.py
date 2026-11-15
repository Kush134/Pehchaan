"""Product-level synthetic retail ledger and auditable stock batches."""
from datetime import date, datetime
from sqlalchemy import String,Integer,Float,Date,DateTime,ForeignKey,JSON,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.database.session import Base
from app.models import uid,now

class StockBatch(Base):
    __tablename__='stock_batches'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    product_id:Mapped[str]=mapped_column(ForeignKey('products.id'),index=True)
    batch_number:Mapped[str]=mapped_column(String)
    quantity_remaining:Mapped[int]=mapped_column(Integer)
    cost_price:Mapped[float]=mapped_column(Float)
    expires_on:Mapped[date|None]=mapped_column(Date,nullable=True,index=True)
    received_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class RetailSale(Base):
    __tablename__='retail_sales'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    customer_token:Mapped[str]=mapped_column(ForeignKey('customer_tokens.customer_token'),index=True)
    transaction_id:Mapped[str]=mapped_column(ForeignKey('transactions.id'),unique=True)
    total_amount:Mapped[float]=mapped_column(Float)
    gross_profit:Mapped[float]=mapped_column(Float)
    payment_method:Mapped[str]=mapped_column(String,default='cash')
    amount_paid:Mapped[float]=mapped_column(Float)
    source:Mapped[str]=mapped_column(String,default='quick-sale')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)

class RetailSaleLine(Base):
    __tablename__='retail_sale_lines'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    sale_id:Mapped[str]=mapped_column(ForeignKey('retail_sales.id'),index=True)
    product_id:Mapped[str]=mapped_column(ForeignKey('products.id'),index=True)
    product_name:Mapped[str]=mapped_column(String)
    variant:Mapped[str]=mapped_column(String,default='Standard')
    quantity:Mapped[int]=mapped_column(Integer)
    unit_price:Mapped[float]=mapped_column(Float)
    unit_cost:Mapped[float]=mapped_column(Float)
    line_total:Mapped[float]=mapped_column(Float)
    line_profit:Mapped[float]=mapped_column(Float)

class StockMovement(Base):
    __tablename__='stock_movements'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    product_id:Mapped[str]=mapped_column(ForeignKey('products.id'),index=True)
    batch_id:Mapped[str|None]=mapped_column(ForeignKey('stock_batches.id'),nullable=True)
    sale_id:Mapped[str|None]=mapped_column(ForeignKey('retail_sales.id'),nullable=True,index=True)
    quantity_delta:Mapped[int]=mapped_column(Integer)
    reason:Mapped[str]=mapped_column(String)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class SupplierReorder(Base):
    __tablename__='supplier_reorders'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    supplier:Mapped[str]=mapped_column(String)
    status:Mapped[str]=mapped_column(String,default='draft')
    items:Mapped[list]=mapped_column(JSON)
    estimated_cost:Mapped[float]=mapped_column(Float)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    received_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
