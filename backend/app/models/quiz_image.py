from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class QuizImage(Base):
    """
    Stochează imaginile descărcate de pe Unsplash pentru quiz-ul v3 (swipe-based).

    Fiecare rând reprezintă o imagine descărcată pentru o anumită categorie mid-level
    din taxonomie (ex: 'mountain', 'nightlife'). CLIP rulează offline pe fiecare imagine
    și salvează scorurile per tag în `clip_tags` JSONB — astfel quizul nu depinde de
    CLIP la runtime (latență zero la prezentarea imaginii).

    Relația cu taxonomia: source_category corespunde unui slug de categorie
    (cat-mountain, cat-beach etc.) dar e stocat ca string simplu pentru flexibilitate.

    Atribuirea fotografului este obligatorie prin licența Unsplash API Terms of Service.
    """
    __tablename__ = "quiz_images"

    id = Column(Integer, primary_key=True, index=True)

    # Locația pe disc — path relativ față de directorul static/ al backend-ului
    # Ex: "quiz-images-v3/mountain/mountain_1.jpg"
    file_path = Column(String, nullable=False, unique=True)

    # Categoria taxonomiei pentru care a fost căutată imaginea
    # Ex: "mountain", "nightlife", "culture and history"
    source_category = Column(String, nullable=False, index=True)

    # Metadate Unsplash (necesare pentru atribuire conform licenței)
    source_url = Column(String, nullable=False)          # URL pagina imaginii pe Unsplash
    photographer = Column(String, nullable=False)         # Numele fotografului
    photographer_url = Column(String, nullable=False)     # Profilul fotografului pe Unsplash
    description = Column(Text, nullable=True)             # Descrierea opțională a imaginii

    # Dimensiuni originale
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)

    # CLIP scores precomputed — {"alpine": 0.85, "snow": 0.78, "hiking": 0.65}
    # JSONB permite indexare și query-uri pe conținut în PostgreSQL
    # Null înseamnă că CLIP nu a rulat încă pe această imagine
    clip_tags = Column(JSONB, nullable=True)
    clip_processed_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    downloaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Flag soft-delete — dezactivează imaginea fără a o șterge (util dacă o imagine
    # devine nepotrivită sau Unsplash o retrage, fără a pierde referința)
    is_active = Column(Boolean, default=True, nullable=False)
