"""Offer SMS delivery state linked to existing single-use customer offers."""
from alembic import op
import sqlalchemy as sa
revision='e20b20112605'
down_revision='d20b20112604'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('sms_notifications',sa.Column('id',sa.String(),sa.ForeignKey('telephony_calls.id'),primary_key=True),sa.Column('campaign_id',sa.String(),sa.ForeignKey('campaigns.id'),nullable=False),sa.Column('status',sa.String(),nullable=False),sa.Column('body',sa.String(),nullable=False),sa.Column('provider_sid',sa.String(),nullable=True,unique=True),sa.Column('simulated',sa.Boolean(),nullable=False),sa.Column('error',sa.String(),nullable=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_sms_notifications_campaign_id','sms_notifications',['campaign_id'])

def downgrade():op.drop_table('sms_notifications')
