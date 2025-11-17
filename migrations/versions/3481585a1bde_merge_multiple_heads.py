"""merge multiple heads

Revision ID: 3481585a1bde
Revises: add_login_security, add_login_security_v2, add_security_columns_v3, c599cf877ff8
Create Date: 2025-05-06 21:34:53.215987

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3481585a1bde'
down_revision = ('add_login_security', 'add_login_security_v2', 'add_security_columns_v3', 'c599cf877ff8')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
