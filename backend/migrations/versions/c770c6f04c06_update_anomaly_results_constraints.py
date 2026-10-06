"""update_anomaly_results_constraints

Revision ID: c770c6f04c06
Revises: b770c6f04c05
Create Date: 2026-10-07 03:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c770c6f06'
down_revision: Union[str, None] = 'b770c6f05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update chk_anomaly_decision to allow UNAVAILABLE and ESCALATE
    op.drop_constraint('chk_anomaly_decision', 'anomaly_results', type_='check')
    op.create_check_constraint(
        'chk_anomaly_decision',
        'anomaly_results',
        "decision IN ('NO_FLAG','REVIEW','SUSPICIOUS','UNAVAILABLE','ESCALATE')"
    )

    # Add unique constraint on entry_id to prevent duplicate anomaly results
    op.create_unique_constraint(
        'uq_anomaly_results_entry_id',
        'anomaly_results',
        ['entry_id']
    )


def downgrade() -> None:
    op.drop_constraint('uq_anomaly_results_entry_id', 'anomaly_results', type_='unique')
    op.drop_constraint('chk_anomaly_decision', 'anomaly_results', type_='check')
    op.create_check_constraint(
        'chk_anomaly_decision',
        'anomaly_results',
        "decision IN ('NO_FLAG','REVIEW','SUSPICIOUS')"
    )
