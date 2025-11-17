"""empty message

Revision ID: c599cf877ff8
Revises: 6feb4c506c7f, add_security_columns
Create Date: 2025-05-02 10:47:32.372719

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c599cf877ff8'
down_revision = ('6feb4c506c7f', 'add_security_columns')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
