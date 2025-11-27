"""Add call_records table for telephony call history.

Revision ID: 007_add_call_records
Revises: 006_add_voice_to_agents
Create Date: 2024-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_add_call_records"
down_revision: str | None = "006_add_voice_to_agents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create call_records table."""
    op.create_table(
        "call_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            nullable=False,
            comment="Owner user ID",
        ),
        sa.Column(
            "provider",
            sa.String(50),
            nullable=False,
            comment="Telephony provider: twilio or telnyx",
        ),
        sa.Column(
            "provider_call_id",
            sa.String(255),
            nullable=False,
            comment="Provider call ID (CallSid for Twilio, call_control_id for Telnyx)",
        ),
        sa.Column(
            "agent_id",
            sa.Uuid(),
            nullable=True,
            comment="Agent that handled the call",
        ),
        sa.Column(
            "contact_id",
            sa.BigInteger(),
            nullable=True,
            comment="CRM contact if applicable",
        ),
        sa.Column(
            "direction",
            sa.String(20),
            nullable=False,
            comment="Call direction: inbound or outbound",
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="initiated",
            comment="Call status",
        ),
        sa.Column(
            "from_number",
            sa.String(50),
            nullable=False,
            comment="Caller phone number",
        ),
        sa.Column(
            "to_number",
            sa.String(50),
            nullable=False,
            comment="Recipient phone number",
        ),
        sa.Column(
            "duration_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Call duration in seconds",
        ),
        sa.Column(
            "recording_url",
            sa.Text(),
            nullable=True,
            comment="URL to call recording",
        ),
        sa.Column(
            "transcript",
            sa.Text(),
            nullable=True,
            comment="Call transcript",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="When the call was initiated",
        ),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the call was answered",
        ),
        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the call ended",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            ondelete="SET NULL",
        ),
    )

    # Create indexes for common queries
    op.create_index("ix_call_records_user_id", "call_records", ["user_id"])
    op.create_index("ix_call_records_agent_id", "call_records", ["agent_id"])
    op.create_index("ix_call_records_contact_id", "call_records", ["contact_id"])
    op.create_index("ix_call_records_provider_call_id", "call_records", ["provider_call_id"])
    op.create_index(
        "ix_call_records_user_started_at",
        "call_records",
        ["user_id", "started_at"],
    )


def downgrade() -> None:
    """Drop call_records table."""
    op.drop_index("ix_call_records_user_started_at", "call_records")
    op.drop_index("ix_call_records_provider_call_id", "call_records")
    op.drop_index("ix_call_records_contact_id", "call_records")
    op.drop_index("ix_call_records_agent_id", "call_records")
    op.drop_index("ix_call_records_user_id", "call_records")
    op.drop_table("call_records")
