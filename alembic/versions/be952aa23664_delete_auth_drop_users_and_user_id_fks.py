"""delete auth: drop users and user_id fks

Revision ID: be952aa23664
Revises: 1916d0f45bf3
Create Date: 2026-08-26 23:43:11.627114

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'be952aa23664'
down_revision: Union[str, Sequence[str], None] = '1916d0f45bf3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the child-side foreign keys and user_id columns first, then the users table.
    # Autogenerate ordered drop_table('users') first, but with ondelete=CASCADE on the
    # FKs, deleting users rows (which DROP TABLE does implicitly under foreign_keys=ON)
    # would cascade-delete every track and playlist. Severing the columns first makes
    # the table drop safe on populated databases.
    with op.batch_alter_table('tracks', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_tracks_user_id_users'), type_='foreignkey')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_playlists_user_id_users'), type_='foreignkey')
        batch_op.drop_column('user_id')

    op.drop_table('users')


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate users before re-adding the foreign keys that reference it.
    op.create_table(
        'users',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('username', sa.VARCHAR(), nullable=False),
        sa.Column('password_hash', sa.VARCHAR(), nullable=False),
        sa.Column('created_at', sa.DATETIME(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('username', name=op.f('uq_users_username')),
    )
    with op.batch_alter_table('tracks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_tracks_user_id_users'), 'users', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_playlists_user_id_users'), 'users', ['user_id'], ['id'], ondelete='CASCADE')
