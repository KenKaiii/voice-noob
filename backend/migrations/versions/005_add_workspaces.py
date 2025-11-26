"""Add workspaces and agent_workspaces tables, add workspace_id to CRM models

Revision ID: 005_add_workspaces
Revises: 657413e72bb1
Create Date: 2025-11-26

This migration:
1. Creates the workspaces table for organizing agents and CRM data
2. Creates the agent_workspaces junction table for many-to-many agent-workspace relationships
3. Adds workspace_id columns to contacts, appointments, and call_interactions
4. Creates a default workspace for each existing user
5. Migrates existing CRM data to the default workspace
"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "005_add_workspaces"
down_revision: Union[str, Sequence[str], None] = "657413e72bb1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create workspaces table
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workspaces_user_id", "workspaces", ["user_id"])
    op.create_index("ix_workspaces_is_default", "workspaces", ["is_default"])

    # 2. Create agent_workspaces junction table
    op.create_table(
        "agent_workspaces",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("agent_id", sa.Uuid(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agent_id", "workspace_id", name="uq_agent_workspace"),
    )
    op.create_index("ix_agent_workspaces_agent_id", "agent_workspaces", ["agent_id"])
    op.create_index("ix_agent_workspaces_workspace_id", "agent_workspaces", ["workspace_id"])

    # 3. Add workspace_id columns to CRM tables (nullable for now)
    op.add_column(
        "contacts",
        sa.Column("workspace_id", sa.Uuid(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_contacts_workspace_id", "contacts", ["workspace_id"])

    op.add_column(
        "appointments",
        sa.Column("workspace_id", sa.Uuid(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("agent_id", sa.Uuid(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_appointments_workspace_id", "appointments", ["workspace_id"])
    op.create_index("ix_appointments_agent_id", "appointments", ["agent_id"])

    op.add_column(
        "call_interactions",
        sa.Column("workspace_id", sa.Uuid(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_call_interactions_workspace_id", "call_interactions", ["workspace_id"])

    # 4. Create default workspaces for existing users and migrate data
    # This is done via raw SQL for efficiency
    connection = op.get_bind()

    # Get all users (users.id is integer)
    users = connection.execute(sa.text("SELECT id FROM users")).fetchall()

    # Track which agent user_ids have been processed (agents.user_id is UUID from Clerk)
    processed_agent_user_ids: set[str] = set()

    for (user_id,) in users:
        # Create default workspace for each user
        workspace_id = uuid.uuid4()
        connection.execute(
            sa.text("""
                INSERT INTO workspaces (id, user_id, name, description, settings, is_default, created_at, updated_at)
                VALUES (:id, :user_id, 'Default Workspace', 'Your default workspace', '{}', true, NOW(), NOW())
            """),
            {"id": workspace_id, "user_id": user_id}
        )

        # Update contacts for this user to use the default workspace
        connection.execute(
            sa.text("UPDATE contacts SET workspace_id = :workspace_id WHERE user_id = :user_id"),
            {"workspace_id": workspace_id, "user_id": user_id}
        )

        # Update appointments via contacts (appointments belong to contacts which belong to users)
        connection.execute(
            sa.text("""
                UPDATE appointments
                SET workspace_id = :workspace_id
                WHERE contact_id IN (SELECT id FROM contacts WHERE user_id = :user_id)
            """),
            {"workspace_id": workspace_id, "user_id": user_id}
        )

        # Update call_interactions via contacts
        connection.execute(
            sa.text("""
                UPDATE call_interactions
                SET workspace_id = :workspace_id
                WHERE contact_id IN (SELECT id FROM contacts WHERE user_id = :user_id)
            """),
            {"workspace_id": workspace_id, "user_id": user_id}
        )

    # Handle agents separately - agents.user_id is a UUID (from Clerk auth)
    # They may not have corresponding entries in the users table
    # Get all unique agent user_ids
    agent_user_ids = connection.execute(
        sa.text("SELECT DISTINCT user_id FROM agents")
    ).fetchall()

    for (agent_user_id,) in agent_user_ids:
        # Check if this agent_user_id already has a workspace via the users table
        # Since agents use Clerk auth UUIDs, we create workspaces per unique agent user_id
        agent_user_id_str = str(agent_user_id)

        if agent_user_id_str in processed_agent_user_ids:
            continue
        processed_agent_user_ids.add(agent_user_id_str)

        # Check if a workspace already exists for this user (e.g., if there's a user with matching ID)
        # Since users.id is integer and agents.user_id is UUID, they won't match
        # Create a workspace for agent users that don't have one
        workspace_id = uuid.uuid4()

        # We need to get a user_id to create the workspace. Use user_id = 1 as a fallback
        # or create a mapping. For now, let's just link agents directly to workspaces.
        # Actually, we should check if there are any users at all, and use the first one
        first_user = connection.execute(sa.text("SELECT id FROM users LIMIT 1")).fetchone()
        if first_user:
            owner_user_id = first_user[0]

            # Create workspace for this agent user
            connection.execute(
                sa.text("""
                    INSERT INTO workspaces (id, user_id, name, description, settings, is_default, created_at, updated_at)
                    VALUES (:id, :user_id, 'Agent Workspace', 'Workspace for voice agents', '{}', false, NOW(), NOW())
                """),
                {"id": workspace_id, "user_id": owner_user_id}
            )

            # Link all agents with this user_id to the workspace
            agents = connection.execute(
                sa.text("SELECT id FROM agents WHERE user_id = :user_id"),
                {"user_id": agent_user_id}
            ).fetchall()

            for (agent_id,) in agents:
                connection.execute(
                    sa.text("""
                        INSERT INTO agent_workspaces (id, agent_id, workspace_id, is_default, created_at, updated_at)
                        VALUES (:id, :agent_id, :workspace_id, true, NOW(), NOW())
                    """),
                    {"id": uuid.uuid4(), "agent_id": agent_id, "workspace_id": workspace_id}
                )


def downgrade() -> None:
    # Remove indexes first
    op.drop_index("ix_call_interactions_workspace_id", table_name="call_interactions")
    op.drop_index("ix_appointments_agent_id", table_name="appointments")
    op.drop_index("ix_appointments_workspace_id", table_name="appointments")
    op.drop_index("ix_contacts_workspace_id", table_name="contacts")

    # Remove columns from CRM tables
    op.drop_column("call_interactions", "workspace_id")
    op.drop_column("appointments", "agent_id")
    op.drop_column("appointments", "workspace_id")
    op.drop_column("contacts", "workspace_id")

    # Drop junction table
    op.drop_index("ix_agent_workspaces_workspace_id", table_name="agent_workspaces")
    op.drop_index("ix_agent_workspaces_agent_id", table_name="agent_workspaces")
    op.drop_table("agent_workspaces")

    # Drop workspaces table
    op.drop_index("ix_workspaces_is_default", table_name="workspaces")
    op.drop_index("ix_workspaces_user_id", table_name="workspaces")
    op.drop_table("workspaces")
