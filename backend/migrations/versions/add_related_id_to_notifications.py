"""add related_id to notifications

Revision ID: add_related_id_to_notifications
Revises: 
Create Date: 2024-03-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_related_id_to_notifications'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notifications', sa.Column('related_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('notifications', 'related_id') 