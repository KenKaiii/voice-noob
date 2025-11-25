"""Add user integrations table for MCP credentials

Revision ID: a7176cbf6e3a
Revises: b95964699e02
Create Date: 2025-11-24 15:11:09.743265

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7176cbf6e3a'
down_revision: Union[str, Sequence[str], None] = 'b95964699e02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'user_integrations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('integration_id', sa.String(length=100), nullable=False),
        sa.Column('integration_name', sa.String(length=200), nullable=False),
        sa.Column('credentials', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('integration_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_integrations_user_id'), 'user_integrations', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_integrations_integration_id'), 'user_integrations', ['integration_id'], unique=False)
    op.create_index('ix_user_integrations_user_integration', 'user_integrations', ['user_id', 'integration_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_user_integrations_user_integration', table_name='user_integrations')
    op.drop_index(op.f('ix_user_integrations_integration_id'), table_name='user_integrations')
    op.drop_index(op.f('ix_user_integrations_user_id'), table_name='user_integrations')
    op.drop_table('user_integrations')
