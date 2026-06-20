from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


class RecommendationImpression(Base):
    __tablename__ = "recommendation_impressions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    surface = Column(String, nullable=False, default="dashboard")
    model_version = Column(String, nullable=False)
    ranking = Column(JSONB, nullable=False, default=list)
    context = Column(JSONB, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
