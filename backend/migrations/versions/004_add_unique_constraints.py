"""Add unique constraints and standalone created_at index

Revision ID: 004_add_unique_constraints
Revises: 003_add_performance_indexes
Create Date: 2025-11-24

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004_add_unique_constraints"
down_revision: Union[str, None] = "003_add_performance_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraints and indexes for data integrity and performance."""
    # Add unique constraint for email + user_id combination
    op.create_index(
        "ix_contacts_user_id_email_unique",
        "contacts",
        ["user_id", "email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )

    # Add unique constraint for phone_number + user_id combination
    op.create_index(
        "ix_contacts_user_id_phone_unique",
        "contacts",
        ["user_id", "phone_number"],
        unique=True,
    )

    # Add standalone created_at index for global list queries without user_id filter
    op.create_index(
        "ix_contacts_created_at",
        "contacts",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove unique constraints and indexes."""
    # Drop standalone created_at index
    op.drop_index("ix_contacts_created_at", table_name="contacts")

    # Drop unique constraints
    op.drop_index("ix_contacts_user_id_phone_unique", table_name="contacts")
    op.drop_index("ix_contacts_user_id_email_unique", table_name="contacts")
