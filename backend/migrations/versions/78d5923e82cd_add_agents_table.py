"""Add agents table

Revision ID: 78d5923e82cd
Revises: a7176cbf6e3a
Create Date: 2025-11-24 15:52:05.548231

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78d5923e82cd'
down_revision: Union[str, Sequence[str], None] = 'a7176cbf6e3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'agents',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('pricing_tier', sa.String(length=50), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en-US'),
        sa.Column('enabled_tools', sa.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('phone_number_id', sa.String(length=100), nullable=True),
        sa.Column('enable_recording', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('enable_transcript', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('provider_config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('total_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_duration_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_call_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agents_user_id'), 'agents', ['user_id'], unique=False)
    op.create_index(op.f('ix_agents_pricing_tier'), 'agents', ['pricing_tier'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_agents_pricing_tier'), table_name='agents')
    op.drop_index(op.f('ix_agents_user_id'), table_name='agents')
    op.drop_table('agents')
