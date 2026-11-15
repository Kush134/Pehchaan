"""Product-level sales, expiry batches, stock movements and supplier reorder drafts."""
from alembic import op
import sqlalchemy as sa
revision='c20b20112603'
down_revision='b20b20112602'
branch_labels=None
depends_on=None

def upgrade():
    for name,kind,default in [('sku',sa.String(),''),('barcode',sa.String(),''),('variant',sa.String(),'Standard'),('reorder_point',sa.Integer(),'20')]:
        op.add_column('products',sa.Column(name,kind,nullable=False,server_default=default))
    op.execute('UPDATE products SET sku = id')
    op.create_table('stock_batches',sa.Column('id',sa.String(),primary_key=True),sa.Column('product_id',sa.String(),sa.ForeignKey('products.id'),nullable=False),sa.Column('batch_number',sa.String(),nullable=False),sa.Column('quantity_remaining',sa.Integer(),nullable=False),sa.Column('cost_price',sa.Float(),nullable=False),sa.Column('expires_on',sa.Date(),nullable=True),sa.Column('received_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_stock_batches_product_id','stock_batches',['product_id']);op.create_index('ix_stock_batches_expires_on','stock_batches',['expires_on'])
    op.create_table('retail_sales',sa.Column('id',sa.String(),primary_key=True),sa.Column('customer_token',sa.String(),sa.ForeignKey('customer_tokens.customer_token'),nullable=False),sa.Column('transaction_id',sa.String(),sa.ForeignKey('transactions.id'),nullable=False,unique=True),sa.Column('total_amount',sa.Float(),nullable=False),sa.Column('gross_profit',sa.Float(),nullable=False),sa.Column('payment_method',sa.String(),nullable=False),sa.Column('amount_paid',sa.Float(),nullable=False),sa.Column('source',sa.String(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_retail_sales_customer_token','retail_sales',['customer_token']);op.create_index('ix_retail_sales_created_at','retail_sales',['created_at'])
    op.create_table('retail_sale_lines',sa.Column('id',sa.String(),primary_key=True),sa.Column('sale_id',sa.String(),sa.ForeignKey('retail_sales.id'),nullable=False),sa.Column('product_id',sa.String(),sa.ForeignKey('products.id'),nullable=False),sa.Column('product_name',sa.String(),nullable=False),sa.Column('variant',sa.String(),nullable=False),sa.Column('quantity',sa.Integer(),nullable=False),sa.Column('unit_price',sa.Float(),nullable=False),sa.Column('unit_cost',sa.Float(),nullable=False),sa.Column('line_total',sa.Float(),nullable=False),sa.Column('line_profit',sa.Float(),nullable=False))
    op.create_index('ix_retail_sale_lines_sale_id','retail_sale_lines',['sale_id']);op.create_index('ix_retail_sale_lines_product_id','retail_sale_lines',['product_id'])
    op.create_table('stock_movements',sa.Column('id',sa.String(),primary_key=True),sa.Column('product_id',sa.String(),sa.ForeignKey('products.id'),nullable=False),sa.Column('batch_id',sa.String(),sa.ForeignKey('stock_batches.id'),nullable=True),sa.Column('sale_id',sa.String(),sa.ForeignKey('retail_sales.id'),nullable=True),sa.Column('quantity_delta',sa.Integer(),nullable=False),sa.Column('reason',sa.String(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_stock_movements_product_id','stock_movements',['product_id']);op.create_index('ix_stock_movements_sale_id','stock_movements',['sale_id'])
    op.create_table('supplier_reorders',sa.Column('id',sa.String(),primary_key=True),sa.Column('supplier',sa.String(),nullable=False),sa.Column('status',sa.String(),nullable=False),sa.Column('items',sa.JSON(),nullable=False),sa.Column('estimated_cost',sa.Float(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('received_at',sa.DateTime(timezone=True),nullable=True))
    # Existing stock is an opening balance, never fabricated dated purchases.
    op.execute("INSERT INTO stock_batches (id,product_id,batch_number,quantity_remaining,cost_price,received_at) SELECT 'opening-' || id,id,'Opening balance',available_stock,purchase_price,CURRENT_TIMESTAMP FROM products WHERE available_stock > 0")

def downgrade():
    for name in ['supplier_reorders','stock_movements','retail_sale_lines','retail_sales','stock_batches']:op.drop_table(name)
    for name in ['reorder_point','variant','barcode','sku']:op.drop_column('products',name)
