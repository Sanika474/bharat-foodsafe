"""add outbox dedupe key and notification fk

Revision ID: d770c6f04c07
Revises: c770c6f04c06
Create Date: 2026-10-07 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd770c6f04c07'
down_revision: Union[str, None] = 'c770c6f06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add dedupe_key column and unique constraint to outbox_events
    op.add_column('outbox_events', sa.Column('dedupe_key', sa.String(length=150), nullable=True))
    op.create_unique_constraint('uq_outbox_events_dedupe_key', 'outbox_events', ['dedupe_key'])

    # 2. Add outbox_event_id column, foreign key, and unique constraint to notifications
    op.add_column('notifications', sa.Column('outbox_event_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_notifications_outbox_event_id',
        'notifications',
        'outbox_events',
        ['outbox_event_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_unique_constraint('uq_notifications_user_outbox_event', 'notifications', ['user_id', 'outbox_event_id'])


def downgrade() -> None:
    op.drop_constraint('uq_notifications_user_outbox_event', 'notifications', type_='unique')
    op.drop_constraint('fk_notifications_outbox_event_id', 'notifications', type_='foreignkey')
    op.drop_column('notifications', 'outbox_event_id')

    op.drop_constraint('uq_outbox_events_dedupe_key', 'outbox_events', type_='unique')
    op.drop_column('outbox_events', 'dedupe_key')
