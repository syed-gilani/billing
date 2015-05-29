"""schema_27

Revision ID: 3e4ceae0f397
Revises: 100f25ab057f
Create Date: 2015-04-20 16:42:41.513685

"""

# revision identifiers, used by Alembic.
revision = '3e4ceae0f397'
down_revision = '100f25ab057f'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.create_table(
        'reebill_user',
        sa.Column('reebill_user_id', sa.Integer(), nullable=False),
        sa.Column('identifier', sa.String(length=100), nullable=False,
                  unique=True),
        sa.Column('username', sa.String(length=1000), nullable=False),
        sa.Column('preferences', sa.String(length=1000), nullable=True),
        sa.Column('session_token', sa.String(length=1000), nullable=True),
        sa.Column('password_hash', sa.String(1000), nullable=False),
        sa.Column('salt', sa.String(1000), nullable=False),
        sa.PrimaryKeyConstraint('reebill_user_id')
    )
    op.create_table('supply_group',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('service', sa.Enum('gas', 'electric'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, unique=True),
        sa.UniqueConstraint('supplier_id', 'name'),
        sa.ForeignKeyConstraint(['supplier_id'], ['supplier.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.add_column('utility', sa.Column('sos_supplier_id', sa.Integer(),
        sa.ForeignKey('supplier.id', ondelete='CASCADE'), nullable=True,
        unique=True))
    op.add_column('utilbill', sa.Column('supply_group_id', sa.Integer(), sa.ForeignKey('supply_group.id'), nullable=True))
    op.add_column('reebill_customer', sa.Column('payee', sa.String(length=100), nullable=False, default='Nextility'))
    op.add_column('utility_account', sa.Column('fb_supply_group_id', sa.Integer(), sa.ForeignKey('supply_group.id'),nullable=True))
    op.add_column('rate_class', sa.Column('sos_supply_group_id', sa.Integer(),
                                          sa.ForeignKey('supply_group.id',
                                                        ondelete='CASCADE'),
                                          nullable=True))

    op.create_table('be_user_session',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_start', sa.DateTime(), nullable=False),
    sa.Column('last_request', sa.DateTime(), nullable=True),
    sa.Column('billentry_user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['billentry_user_id'], ['billentry_user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_unique_constraint(None, 'utility', ['name'])
    op.create_unique_constraint(None, 'rate_class', ['utility_id', 'name'])
    op.create_unique_constraint(None, 'supplier', ['name'])
    # supply_group unique constraint was specified above

def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_unique_constraint(u'account', 'utility_account', ['account'])
    op.create_unique_constraint(u'name', 'utility', ['name'])
    op.create_unique_constraint(u'name', 'supplier', ['name'])
    op.create_unique_constraint(u'utilbill_id', 'register', ['utilbill_id', 'register_binding'])
    op.alter_column('register', 'register_binding',
               existing_type=mysql.ENUM(u'REG_TOTAL', u'REG_TOTAL_SECONDARY', u'REG_TOTAL_TERTIARY', u'REG_PEAK', u'REG_INTERMEDIATE', u'REG_OFFPEAK', u'REG_DEMAND', u'REG_POWERFACTOR', u'REG_PEAK_RATE_INCREASE', u'REG_INTERMEDIATE_RATE_INCREASE', u'REG_OFFPEAK_RATE_INCREASE', u'FIRST_MONTH_THERMS', u'SECOND_MONTH_THERMS', u'BEGIN_INVENTORY', u'END_INVENTORY', u'CONTRACT_VOLUME'),
               nullable=True)
    op.create_unique_constraint(u'identifier', 'reebill_user', ['identifier'])
    op.alter_column('reebill_customer', 'payee',
               existing_type=mysql.VARCHAR(length=100),
               nullable=True)


    op.drop_column('utility', 'sos_supply_group_id')
    op.drop_column('utility_account', 'fb_supply_group_id')
    op.drop_column('reebill_customer', 'payee')
    op.drop_column('utilbill', 'supply_group_id')
    op.drop_table('supply_group')
    op.drop_table('reebill_user')
    ### end Alembic commands ###


