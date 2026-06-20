"""move feedback schema changes out of application startup

Revision ID: 20260605_0001
Revises:
Create Date: 2026-06-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260605_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These statements intentionally use IF NOT EXISTS because this project
    # already had a live schema before Alembic was introduced.
    op.execute("ALTER TABLE quiz_v4_sessions ADD COLUMN IF NOT EXISTS tag_beliefs JSONB")
    op.execute("ALTER TABLE quiz_v4_sessions ADD COLUMN IF NOT EXISTS pace_preference VARCHAR")
    op.execute("ALTER TABLE itinerary_plans ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'auto'")
    op.execute(
        "ALTER TABLE itinerary_plans ADD COLUMN IF NOT EXISTS created_at "
        "TIMESTAMPTZ DEFAULT NOW()"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS itinerary_ratings (
            id SERIAL PRIMARY KEY,
            plan_id INTEGER NOT NULL REFERENCES itinerary_plans(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            rating INTEGER NOT NULL,
            aspects JSON,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_itinerary_ratings_id ON itinerary_ratings (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_itinerary_ratings_plan_id ON itinerary_ratings (plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_itinerary_ratings_user_id ON itinerary_ratings (user_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendation_impressions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            session_id VARCHAR NOT NULL,
            surface VARCHAR NOT NULL DEFAULT 'dashboard',
            model_version VARCHAR NOT NULL,
            ranking JSONB NOT NULL,
            context JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_recommendation_impressions_id ON recommendation_impressions (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recommendation_impressions_user_id ON recommendation_impressions (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recommendation_impressions_session_id ON recommendation_impressions (session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recommendation_impressions_created_at ON recommendation_impressions (created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recommendation_impressions")
    op.execute("DROP TABLE IF EXISTS itinerary_ratings")
    op.execute("ALTER TABLE itinerary_plans DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE itinerary_plans DROP COLUMN IF EXISTS source")
    op.execute("ALTER TABLE quiz_v4_sessions DROP COLUMN IF EXISTS pace_preference")
    op.execute("ALTER TABLE quiz_v4_sessions DROP COLUMN IF EXISTS tag_beliefs")
