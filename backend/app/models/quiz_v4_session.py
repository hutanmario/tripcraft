"""
app/models/quiz_v4_session.py
=============================
Model pentru sesiunile quiz v4 — adaptive, bazat pe geografia nouă.
"""

import uuid
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class QuizV4Session(Base):
    __tablename__ = "quiz_v4_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # 'swipe' → 'clarify' → 'completed'
    current_stage = Column(String, nullable=False, default="swipe")

    # Cardurile deja arătate: [tag_slug, ...]
    shown_tags = Column(JSONB, nullable=False, default=list)

    # Imaginile deja arătate: [unsplash_id, ...]
    shown_images = Column(JSONB, nullable=False, default=list)

    # Rezultatele swipe: {tag_slug: 1|-1} (1=right, -1=left)
    swipe_results = Column(JSONB, nullable=False, default=dict)

    # Profilul acumulat: {tag_slug: float} — actualizat după fiecare swipe
    tag_scores = Column(JSONB, nullable=False, default=dict)

    # Bayesian beliefs: {tag_slug: {"alpha": float, "beta": float}}
    # None → legacy session (old linear accumulation)
    tag_beliefs = Column(JSONB, nullable=True, default=None)

    # Numărul de carduri arătate
    card_count = Column(Integer, nullable=False, default=0)

    # Entropia profilului la ultimul calcul
    last_entropy = Column(String, nullable=True)

    # Întrebările de clarificare generate
    clarify_questions = Column(JSONB, nullable=True)

    # Răspunsurile la clarify: [{question_id, answer}, ...]
    clarify_answers = Column(JSONB, nullable=True)

    # Profilul final: {tag_slug: float}
    final_profile = Column(JSONB, nullable=True)

    # Budget și sezon (obligatorii)
    budget = Column(String, nullable=True)       # 'budget'|'mid'|'luxury'
    season = Column(String, nullable=True)        # 'spring'|'summer'|'autumn'|'winter'
    travel_style = Column(String, nullable=True)  # 'solo'|'couple'|'family'|'group'
    pace_preference = Column(String, nullable=True)  # 'relaxed'|'balanced'|'packed'

    user = relationship("User", backref="quiz_v4_sessions")
