"""pg_export_altitude

Revision ID: 556352363426
Revises: 5a6d7e4f8b80
Create Date: 2015-01-14 14:17:39.571664

All data model changes related to exporting a CSV file of PG-related data for Altitude (BILL-5937).
"""

# revision identifiers, used by Alembic.
revision = '556352363426'
down_revision = '3cf530e68eb'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('pg_account',
        sa.Column('utility_account_id', sa.Integer(), primary_key=True),
        sa.ForeignKeyConstraint(['utility_account_id'], ['utility_account.id'], ),
    )
    op.add_column(u'utilbill',
                  sa.Column('date_modified', sa.DateTime(), nullable=True))
    op.add_column(u'utilbill',
                  sa.Column('supply_choice_id', sa.String(1000), nullable=True))
    op.add_column(u'charge',
                  sa.Column('type', sa.Enum('supply', 'distribution', 'other'),
                            nullable=False))
    op.add_column(u'charge', sa.Column('target_total', sa.Float))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column(u'utilbill', 'date_modified')
    op.drop_column(u'utilbill', 'supply_choice_id')
    op.drop_column(u'charge', 'type')
    op.drop_column(u'charge', 'target_total')
    op.drop_table('pg_account')
    ### end Alembic commands ###
