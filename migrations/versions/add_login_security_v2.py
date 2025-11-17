"""add login security columns v2

Revision ID: add_login_security_v2
Revises: 6feb4c506c7f
Create Date: 2024-04-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_login_security_v2'
down_revision = '6feb4c506c7f'
branch_labels = None
depends_on = None

def upgrade():
    # Using raw SQL to add columns if they don't exist
    op.execute("""
        ALTER TABLE user 
        ADD COLUMN IF NOT EXISTS login_attempts INT DEFAULT 0,
        ADD COLUMN IF NOT EXISTS last_login_attempt DATETIME NULL,
        ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS lock_until DATETIME NULL;
    """)

def downgrade():
    # Using raw SQL to remove columns
    op.execute("""
        ALTER TABLE user 
        DROP COLUMN IF EXISTS login_attempts,
        DROP COLUMN IF EXISTS last_login_attempt,
        DROP COLUMN IF EXISTS is_locked,
        DROP COLUMN IF EXISTS lock_until;
    """) 