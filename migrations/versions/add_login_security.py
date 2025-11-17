"""add login security columns

Revision ID: add_login_security
Revises: 6feb4c506c7f
Create Date: 2024-04-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_login_security'
down_revision = '6feb4c506c7f'
branch_labels = None
depends_on = None

def upgrade():
    # Drop columns if they exist to avoid conflicts
    try:
        op.drop_column('user', 'login_attempts')
    except:
        pass
    try:
        op.drop_column('user', 'last_login_attempt')
    except:
        pass
    try:
        op.drop_column('user', 'is_locked')
    except:
        pass
    try:
        op.drop_column('user', 'lock_until')
    except:
        pass

    # Add new columns
    op.add_column('user', sa.Column('login_attempts', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('user', sa.Column('last_login_attempt', sa.DateTime(), nullable=True))
    op.add_column('user', sa.Column('is_locked', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('user', sa.Column('lock_until', sa.DateTime(), nullable=True))

def downgrade():
    # Remove the columns
    op.drop_column('user', 'lock_until')
    op.drop_column('user', 'is_locked')
    op.drop_column('user', 'last_login_attempt')
    op.drop_column('user', 'login_attempts') 