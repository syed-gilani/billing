"""bill validation

Revision ID: 3482c138b392
Revises: 4d54d21b2c7a
Create Date: 2015-08-17 13:32:34.882940

"""

# revision identifiers, used by Alembic.
from core.model import UtilBill

revision = '3482c138b392'
down_revision = '1226d67c4c53'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # # apparently "alter type" to add values to an enum doesn't work in
    # # Alembic, so you can't use op.alter_column(..., type_=...)
    # # https://bitbucket.org/zzzeek/alembic/issue/270/altering-enum-type
    # # AND postgres won't let you run "alter type" inside a transaction either.
    # # https://bitbucket.org/zzzeek/alembic/issue/123/a-way-to-run-non-transactional-ddl

    # add 'identity' to field_type
    connection = op.get_bind()
    connection.execution_options(isolation_level='AUTOCOMMIT')
    op.execute("alter type field_type add value 'identity'")

    validation_state_enum = sa.Enum(*UtilBill.VALIDATION_STATES,
        name='validation_state')
    validation_state_enum.create(op.get_bind(), checkfirst=False)
    op.add_column('utilbill', sa.Column('validation_state',
        validation_state_enum, server_default=UtilBill.FAILED))



def downgrade():
    pass