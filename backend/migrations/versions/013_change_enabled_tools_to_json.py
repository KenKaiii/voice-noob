"""Change enabled_tools from ARRAY to JSON for SQLite compatibility in tests.

Revision ID: 013_change_enabled_tools_to_json
Revises: 012_add_production_indexes
Create Date: 2025-11-29

Note: This migration converts the enabled_tools column from PostgreSQL ARRAY
to JSON type, which is compatible with both PostgreSQL and SQLite.
This allows tests to run with SQLite while production uses PostgreSQL.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "013_change_enabled_tools_to_json"
down_revision = "012_add_production_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert enabled_tools from ARRAY(String) to JSON."""
    # 1. Drop the default value
    op.execute("ALTER TABLE agents ALTER COLUMN enabled_tools DROP DEFAULT;")

    # 2. Convert ARRAY to JSONB
    op.execute(
        """
        ALTER TABLE agents
        ALTER COLUMN enabled_tools TYPE JSONB
        USING to_jsonb(enabled_tools);
        """
    )

    # 3. Set new default for JSONB (empty array as JSON)
    op.execute("ALTER TABLE agents ALTER COLUMN enabled_tools SET DEFAULT '[]'::jsonb;")


def downgrade() -> None:
    """Convert enabled_tools back from JSON to ARRAY(String)."""
    # 1. Drop the JSON default
    op.execute("ALTER TABLE agents ALTER COLUMN enabled_tools DROP DEFAULT;")

    # 2. Convert JSON back to ARRAY
    op.execute(
        """
        ALTER TABLE agents
        ALTER COLUMN enabled_tools TYPE VARCHAR[]
        USING ARRAY(SELECT jsonb_array_elements_text(enabled_tools));
        """
    )

    # 3. Set ARRAY default
    op.execute("ALTER TABLE agents ALTER COLUMN enabled_tools SET DEFAULT '{}'::varchar[];")
