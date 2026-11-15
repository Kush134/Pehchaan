"""Durable retail checkout quotes and simulated payment receipts."""
from alembic import op
import sqlalchemy as sa

revision = 'b20b20112602'
down_revision = 'a20b20112601'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('retail_checkouts',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('retail_checkouts')
