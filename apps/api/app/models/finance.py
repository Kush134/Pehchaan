"""Recorded operating expenses and allocations of repayments against credit sales."""
from datetime import date,datetime
from sqlalchemy import String,Float,Date,DateTime,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from app.database.session import Base
from app.models import uid,now

class Expense(Base):
    __tablename__='business_expenses'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    merchant_id:Mapped[str]=mapped_column(ForeignKey('merchants.id'),index=True)
    category:Mapped[str]=mapped_column(String)
    amount:Mapped[float]=mapped_column(Float)
    description:Mapped[str]=mapped_column(String,default='')
    expense_date:Mapped[date]=mapped_column(Date,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class KhataPayment(Base):
    __tablename__='khata_payments'
    id:Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    customer_token:Mapped[str]=mapped_column(ForeignKey('customer_tokens.customer_token'),index=True)
    sale_id:Mapped[str]=mapped_column(ForeignKey('retail_sales.id'),index=True)
    amount:Mapped[float]=mapped_column(Float)
    payment_method:Mapped[str]=mapped_column(String)
    note:Mapped[str]=mapped_column(String,default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
