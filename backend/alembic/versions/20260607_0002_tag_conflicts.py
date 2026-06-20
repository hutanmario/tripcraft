"""map tag conflicts table

Revision ID: 20260607_0002
Revises: 20260605_0001
Create Date: 2026-06-07
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260607_0002"
down_revision: Union[str, None] = "20260605_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tag_conflicts (
            id SERIAL PRIMARY KEY,
            tag_a_id INTEGER NOT NULL REFERENCES tags(id),
            tag_b_id INTEGER NOT NULL REFERENCES tags(id),
            question TEXT NOT NULL,
            options JSONB NOT NULL,
            CONSTRAINT uq_tag_conflicts_pair UNIQUE (tag_a_id, tag_b_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_tag_conflicts_id ON tag_conflicts (id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tag_conflicts")
