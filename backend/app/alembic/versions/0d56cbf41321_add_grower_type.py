"""add grower type

Revision ID: 0d56cbf41321
Revises: f910ece7c570
Create Date: 2024-06-21 03:42:47.194761

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '0d56cbf41321'
down_revision = 'f910ece7c570'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('grower', sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False))
    op.add_column('grower', sa.Column('company_registration_number', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('grower', sa.Column('company_logo', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.alter_column('grower', 'id_card_number',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('grower', 'id_card_photo',
               existing_type=sa.VARCHAR(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('grower', 'id_card_photo',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('grower', 'id_card_number',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.drop_column('grower', 'company_logo')
    op.drop_column('grower', 'company_registration_number')
    op.drop_column('grower', 'type')
    # ### end Alembic commands ###
