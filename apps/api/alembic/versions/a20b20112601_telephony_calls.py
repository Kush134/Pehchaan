"""Persistent outbound calls and offer acceptance."""
from alembic import op
import sqlalchemy as sa

revision = 'a20b20112601'
down_revision = 'f176b13d4a85'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('telephony_calls',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('campaign_id', sa.String(), sa.ForeignKey('campaigns.id'), nullable=False),
        sa.Column('customer_token', sa.String(), sa.ForeignKey('customer_tokens.customer_token'), nullable=False),
        sa.Column('customer_name', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_attempt_id', sa.String(), nullable=True, unique=True),
        sa.Column('offer_amount', sa.Float(), nullable=False),
        sa.Column('minimum_bill', sa.Float(), nullable=False),
        sa.Column('script', sa.String(), nullable=False),
        sa.Column('audio_base64', sa.String(), nullable=True),
        sa.Column('accepted', sa.Boolean(), nullable=False),
        sa.Column('acceptance_source', sa.String(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('redeemed', sa.Boolean(), nullable=False),
        sa.Column('checkout_id', sa.String(), nullable=True),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('campaign_id', 'customer_token'))
    for column in ('campaign_id', 'customer_token', 'status'):
        op.create_index(f'ix_telephony_calls_{column}', 'telephony_calls', [column])

def downgrade():
    op.drop_table('telephony_calls')
