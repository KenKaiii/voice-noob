"""Merge migration heads

Revision ID: b95964699e02
Revises: 001, 004_add_unique_constraints
Create Date: 2025-11-24 15:11:04.049993

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b95964699e02'
down_revision: Union[str, Sequence[str], None] = ('001', '004_add_unique_constraints')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
