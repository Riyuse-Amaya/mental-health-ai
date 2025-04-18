"""Add psychological_state to ChatHistory

Revision ID: 4b3f00230ae8
Revises: 109d209dc716
Create Date: 2025-04-14 16:53:42.492868

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b3f00230ae8'
down_revision = '109d209dc716'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('chat_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('psychological_state', sa.String(length=20), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('chat_history', schema=None) as batch_op:
        batch_op.drop_column('psychological_state')

    # ### end Alembic commands ###
