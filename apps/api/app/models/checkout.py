"""Durable retail quotes and receipts; all payment execution is simulated."""
from app.database.session import Base
from app.models import WorkflowMixin


class RetailCheckout(WorkflowMixin, Base):
    __tablename__ = 'retail_checkouts'
