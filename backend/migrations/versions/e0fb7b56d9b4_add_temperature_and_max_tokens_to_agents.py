"""add_temperature_and_max_tokens_to_agents

Revision ID: e0fb7b56d9b4
Revises: e665adac48b0
Create Date: 2025-11-28 22:41:20.546419

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0fb7b56d9b4'
down_revision: Union[str, Sequence[str], None] = 'e665adac48b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add temperature and max_tokens columns to agents table."""
    op.add_column('agents', sa.Column('temperature', sa.Float(), nullable=False, server_default='0.7', comment='LLM temperature (0.0-2.0)'))
    op.add_column('agents', sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='2000', comment='Maximum response tokens'))


def downgrade() -> None:
    """Remove temperature and max_tokens columns from agents table."""
    op.drop_column('agents', 'max_tokens')
    op.drop_column('agents', 'temperature')
