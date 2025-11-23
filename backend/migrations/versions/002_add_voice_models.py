"""Add voice agent, integration, phone number, and call models

Revision ID: 002
Revises: 001
Create Date: 2025-11-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create phone_numbers table
    op.create_table(
        'phone_numbers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=False),
        sa.Column('country_code', sa.String(length=5), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('provider_phone_number_id', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_phone_numbers_id'), 'phone_numbers', ['id'], unique=False)
    op.create_index(op.f('ix_phone_numbers_phone_number'), 'phone_numbers', ['phone_number'], unique=True)
    op.create_index(op.f('ix_phone_numbers_user_id'), 'phone_numbers', ['user_id'], unique=False)

    # Create voice_agents table
    op.create_table(
        'voice_agents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('pricing_tier', sa.String(length=50), nullable=False),
        sa.Column('llm_config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('stt_config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('tts_config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('voice_id', sa.String(length=255), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('phone_number_id', sa.Integer(), nullable=True),
        sa.Column('enabled_integrations', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['phone_number_id'], ['phone_numbers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_voice_agents_id'), 'voice_agents', ['id'], unique=False)
    op.create_index(op.f('ix_voice_agents_phone_number_id'), 'voice_agents', ['phone_number_id'], unique=False)
    op.create_index(op.f('ix_voice_agents_user_id'), 'voice_agents', ['user_id'], unique=False)

    # Create integrations table
    op.create_table(
        'integrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('integration_type', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('api_secret', sa.Text(), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expiry', sa.String(length=255), nullable=True),
        sa.Column('account_id', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_integrations_id'), 'integrations', ['id'], unique=False)
    op.create_index(op.f('ix_integrations_integration_type'), 'integrations', ['integration_type'], unique=False)
    op.create_index(op.f('ix_integrations_user_id'), 'integrations', ['user_id'], unique=False)

    # Create calls table
    op.create_table(
        'calls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('voice_agent_id', sa.Integer(), nullable=False),
        sa.Column('phone_number_id', sa.Integer(), nullable=False),
        sa.Column('call_sid', sa.String(length=255), nullable=False),
        sa.Column('direction', sa.String(length=20), nullable=False),
        sa.Column('from_number', sa.String(length=20), nullable=False),
        sa.Column('to_number', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('transcript', sa.Text(), nullable=True),
        sa.Column('recording_url', sa.String(length=500), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['phone_number_id'], ['phone_numbers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['voice_agent_id'], ['voice_agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_calls_call_sid'), 'calls', ['call_sid'], unique=True)
    op.create_index(op.f('ix_calls_id'), 'calls', ['id'], unique=False)
    op.create_index(op.f('ix_calls_phone_number_id'), 'calls', ['phone_number_id'], unique=False)
    op.create_index(op.f('ix_calls_status'), 'calls', ['status'], unique=False)
    op.create_index(op.f('ix_calls_user_id'), 'calls', ['user_id'], unique=False)
    op.create_index(op.f('ix_calls_voice_agent_id'), 'calls', ['voice_agent_id'], unique=False)


def downgrade() -> None:
    # Drop calls table
    op.drop_index(op.f('ix_calls_voice_agent_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_user_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_status'), table_name='calls')
    op.drop_index(op.f('ix_calls_phone_number_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_call_sid'), table_name='calls')
    op.drop_table('calls')

    # Drop integrations table
    op.drop_index(op.f('ix_integrations_user_id'), table_name='integrations')
    op.drop_index(op.f('ix_integrations_integration_type'), table_name='integrations')
    op.drop_index(op.f('ix_integrations_id'), table_name='integrations')
    op.drop_table('integrations')

    # Drop voice_agents table
    op.drop_index(op.f('ix_voice_agents_user_id'), table_name='voice_agents')
    op.drop_index(op.f('ix_voice_agents_phone_number_id'), table_name='voice_agents')
    op.drop_index(op.f('ix_voice_agents_id'), table_name='voice_agents')
    op.drop_table('voice_agents')

    # Drop phone_numbers table
    op.drop_index(op.f('ix_phone_numbers_user_id'), table_name='phone_numbers')
    op.drop_index(op.f('ix_phone_numbers_phone_number'), table_name='phone_numbers')
    op.drop_index(op.f('ix_phone_numbers_id'), table_name='phone_numbers')
    op.drop_table('phone_numbers')
