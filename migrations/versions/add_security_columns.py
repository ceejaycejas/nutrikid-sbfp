"""add security columns

Revision ID: add_security_columns
Revises: 
Create Date: 2024-04-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_security_columns'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add new columns to user table
    op.add_column('user', sa.Column('login_attempts', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('user', sa.Column('last_login_attempt', sa.DateTime(), nullable=True))
    op.add_column('user', sa.Column('is_locked', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('user', sa.Column('lock_until', sa.DateTime(), nullable=True))
    
    # Update existing records
    op.execute("UPDATE user SET login_attempts = 0")
    op.execute("UPDATE user SET is_locked = false")

def downgrade():
    # Remove the columns
    op.drop_column('user', 'lock_until')
    op.drop_column('user', 'is_locked')
    op.drop_column('user', 'last_login_attempt')
    op.drop_column('user', 'login_attempts') 