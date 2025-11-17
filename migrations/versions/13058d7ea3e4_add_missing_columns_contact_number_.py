"""add missing columns contact_number email to school and is_beneficiary to student

Revision ID: 13058d7ea3e4
Revises: 7d3b4c8e2f9a
Create Date: 2025-11-16 21:48:21.978700

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '13058d7ea3e4'
down_revision = '7d3b4c8e2f9a'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing columns to school table
    with op.batch_alter_table('school', schema=None) as batch_op:
        # Check if columns exist before adding
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        columns = [col['name'] for col in inspector.get_columns('school')]
        
        if 'contact_number' not in columns:
            batch_op.add_column(sa.Column('contact_number', sa.String(length=20), nullable=True))
        if 'email' not in columns:
            batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=True))
    
    # Add missing column to student table
    with op.batch_alter_table('student', schema=None) as batch_op:
        # Check if column exists before adding
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        columns = [col['name'] for col in inspector.get_columns('student')]
        
        if 'is_beneficiary' not in columns:
            batch_op.add_column(sa.Column('is_beneficiary', sa.Boolean(), nullable=True, server_default='0'))


def downgrade():
    # Remove columns from school table
    with op.batch_alter_table('school', schema=None) as batch_op:
        batch_op.drop_column('email')
        batch_op.drop_column('contact_number')
    
    # Remove column from student table
    with op.batch_alter_table('student', schema=None) as batch_op:
        batch_op.drop_column('is_beneficiary')
