"""Add turn detection settings to agents table.

Revision ID: 008_add_turn_detection_settings
Revises: 007_add_call_records
Create Date: 2024-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008_add_turn_detection_settings"
down_revision: str | None = "007_add_call_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add turn detection columns to agents table."""
    op.add_column(
        "agents",
        sa.Column(
            "turn_detection_mode",
            sa.String(20),
            nullable=False,
            server_default="normal",
            comment="Turn detection mode: normal, semantic, or disabled",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "turn_detection_threshold",
            sa.Float(),
            nullable=False,
            server_default="0.5",
            comment="VAD threshold (0.0-1.0)",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "turn_detection_prefix_padding_ms",
            sa.Integer(),
            nullable=False,
            server_default="300",
            comment="Prefix padding in milliseconds",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "turn_detection_silence_duration_ms",
            sa.Integer(),
            nullable=False,
            server_default="500",
            comment="Silence duration in milliseconds before turn ends",
        ),
    )


def downgrade() -> None:
    """Remove turn detection columns from agents table."""
    op.drop_column("agents", "turn_detection_silence_duration_ms")
    op.drop_column("agents", "turn_detection_prefix_padding_ms")
    op.drop_column("agents", "turn_detection_threshold")
    op.drop_column("agents", "turn_detection_mode")
