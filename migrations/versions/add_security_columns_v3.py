"""add security columns v3

Revision ID: add_security_columns_v3
Revises: 6feb4c506c7f
Create Date: 2024-04-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'add_security_columns_v3'
down_revision = '6feb4c506c7f'
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    
    # Add login_attempts column
    try:
        conn.execute(text("ALTER TABLE user ADD COLUMN login_attempts INT DEFAULT 0"))
    except:
        pass
        
    # Add last_login_attempt column
    try:
        conn.execute(text("ALTER TABLE user ADD COLUMN last_login_attempt DATETIME NULL"))
    except:
        pass
        
    # Add is_locked column
    try:
        conn.execute(text("ALTER TABLE user ADD COLUMN is_locked BOOLEAN DEFAULT FALSE"))
    except:
        pass
        
    # Add lock_until column
    try:
        conn.execute(text("ALTER TABLE user ADD COLUMN lock_until DATETIME NULL"))
    except:
        pass

def downgrade():
    conn = op.get_bind()
    
    # Remove columns
    try:
        conn.execute(text("ALTER TABLE user DROP COLUMN lock_until"))
        conn.execute(text("ALTER TABLE user DROP COLUMN is_locked"))
        conn.execute(text("ALTER TABLE user DROP COLUMN last_login_attempt"))
        conn.execute(text("ALTER TABLE user DROP COLUMN login_attempts"))
    except:
        pass 