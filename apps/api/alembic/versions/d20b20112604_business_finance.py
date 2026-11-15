"""Expense records and credit-sale repayment allocations."""
from alembic import op
import sqlalchemy as sa
revision='d20b20112604'
down_revision='c20b20112603'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('business_expenses',sa.Column('id',sa.String(),primary_key=True),sa.Column('merchant_id',sa.String(),sa.ForeignKey('merchants.id'),nullable=False),sa.Column('category',sa.String(),nullable=False),sa.Column('amount',sa.Float(),nullable=False),sa.Column('description',sa.String(),nullable=False),sa.Column('expense_date',sa.Date(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_business_expenses_merchant_id','business_expenses',['merchant_id']);op.create_index('ix_business_expenses_expense_date','business_expenses',['expense_date'])
    op.create_table('khata_payments',sa.Column('id',sa.String(),primary_key=True),sa.Column('customer_token',sa.String(),sa.ForeignKey('customer_tokens.customer_token'),nullable=False),sa.Column('sale_id',sa.String(),sa.ForeignKey('retail_sales.id'),nullable=False),sa.Column('amount',sa.Float(),nullable=False),sa.Column('payment_method',sa.String(),nullable=False),sa.Column('note',sa.String(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_khata_payments_customer_token','khata_payments',['customer_token']);op.create_index('ix_khata_payments_sale_id','khata_payments',['sale_id'])

def downgrade():
    op.drop_table('khata_payments');op.drop_table('business_expenses')
