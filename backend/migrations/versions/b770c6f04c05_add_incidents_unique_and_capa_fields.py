"""add_incidents_unique_and_capa_fields

Revision ID: b770c6f04c05
Revises: 9770c6f04c04
Create Date: 2026-10-07 03:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b770c6f05'
down_revision: Union[str, None] = '9770c6f04c04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add Unique Constraint on incidents.entry_id for persistent idempotency
    op.create_unique_constraint('uq_incidents_entry_id', 'incidents', ['entry_id'])

    # 2. Add recheck tracking columns to corrective_actions
    op.add_column('corrective_actions', sa.Column('recheck_entry_id', sa.UUID(), nullable=True))
    op.add_column('corrective_actions', sa.Column('evidence_file_id', sa.UUID(), nullable=True))
    op.add_column('corrective_actions', sa.Column('notes', sa.Text(), nullable=True))

    op.create_foreign_key('fk_ca_recheck_entry_id', 'corrective_actions', 'entries', ['recheck_entry_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_ca_evidence_file_id', 'corrective_actions', 'evidence_files', ['evidence_file_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_ca_evidence_file_id', 'corrective_actions', type_='foreignkey')
    op.drop_constraint('fk_ca_recheck_entry_id', 'corrective_actions', type_='foreignkey')
    op.drop_column('corrective_actions', 'notes')
    op.drop_column('corrective_actions', 'evidence_file_id')
    op.drop_column('corrective_actions', 'recheck_entry_id')
    op.drop_constraint('uq_incidents_entry_id', 'incidents', type_='unique')
