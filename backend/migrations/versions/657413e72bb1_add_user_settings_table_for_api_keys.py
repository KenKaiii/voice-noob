"""Add user settings table for API keys

Revision ID: 657413e72bb1
Revises: 78d5923e82cd
Create Date: 2025-11-25 01:12:00.928932

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '657413e72bb1'
down_revision: Union[str, Sequence[str], None] = '78d5923e82cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'user_settings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('openai_api_key', sa.Text(), nullable=True),
        sa.Column('deepgram_api_key', sa.Text(), nullable=True),
        sa.Column('elevenlabs_api_key', sa.Text(), nullable=True),
        sa.Column('telnyx_api_key', sa.Text(), nullable=True),
        sa.Column('telnyx_public_key', sa.Text(), nullable=True),
        sa.Column('twilio_account_sid', sa.String(length=255), nullable=True),
        sa.Column('twilio_auth_token', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_user_settings_user_id'), 'user_settings', ['user_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_user_settings_user_id'), table_name='user_settings')
    op.drop_table('user_settings')
