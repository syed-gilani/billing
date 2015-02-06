"""drop service column from utilbill

Revision ID: 2d65c7c19345
Revises: 5a356721c95e
Create Date: 2015-02-04 11:33:37.069418

"""

# revision identifiers, used by Alembic.
revision = '2d65c7c19345'
down_revision = '5a356721c95e'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('utilbill', 'service')
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('utilbill', sa.Column('service', mysql.VARCHAR(length=45), nullable=False))
    ### end Alembic commands ###