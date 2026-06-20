"""
backend/app/models/geography.py
================================
Modele pentru țări, orașe și atracții turistice.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Text,
    DateTime, ForeignKey, Boolean, Table
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


# ─── Association tables ───────────────────────────────────────────────────────

country_tags = Table(
    "country_tags",
    Base.metadata,
    Column("country_id", Integer, ForeignKey("countries.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
    Column("score", Float, default=1.0),
)

city_tags = Table(
    "city_tags",
    Base.metadata,
    Column("city_id", Integer, ForeignKey("cities.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
    Column("score", Float, default=1.0),
)

attraction_tags = Table(
    "attraction_tags",
    Base.metadata,
    Column("attraction_id", Integer, ForeignKey("attractions.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
    Column("score", Float, default=1.0),
)


# ─── Country ──────────────────────────────────────────────────────────────────

class Country(Base):
    __tablename__ = "countries"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(100), nullable=False, unique=True)
    iso2           = Column(String(2),   nullable=False, unique=True, index=True)
    iso3           = Column(String(3),   nullable=True)
    capital        = Column(String(100), nullable=True)
    latitude       = Column(Float, nullable=True)
    longitude      = Column(Float, nullable=True)
    description    = Column(Text, nullable=True)
    image_url      = Column(String, nullable=True)   # Unsplash URL
    image_credit   = Column(String, nullable=True)
    avg_cost_per_day = Column(Float, nullable=True)  # EUR/zi estimat
    currency       = Column(String(10), nullable=True)
    language       = Column(String(100), nullable=True)
    best_seasons   = Column(String, nullable=True)   # "spring,summer"
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    cities         = relationship("City", back_populates="country", lazy="select")
    tags           = relationship("Tag", secondary=country_tags, lazy="select")


# ─── City ─────────────────────────────────────────────────────────────────────

class City(Base):
    __tablename__ = "cities"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(100), nullable=False)
    country_id     = Column(Integer, ForeignKey("countries.id"), nullable=False, index=True)
    latitude       = Column(Float, nullable=False)
    longitude      = Column(Float, nullable=False)
    population     = Column(Integer, nullable=True)
    description    = Column(Text, nullable=True)
    image_url      = Column(String, nullable=True)
    image_credit   = Column(String, nullable=True)
    avg_cost_per_day = Column(Float, nullable=True)
    is_capital     = Column(Boolean, default=False)
    legacy_tags    = Column(Text, nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    country        = relationship("Country", back_populates="cities")
    attractions    = relationship("Attraction", back_populates="city", lazy="select")
    tags           = relationship("Tag", secondary=city_tags, lazy="select")


# ─── Attraction ───────────────────────────────────────────────────────────────

class Attraction(Base):
    __tablename__ = "attractions"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(200), nullable=False)
    city_id        = Column(Integer, ForeignKey("cities.id"), nullable=False, index=True)
    latitude       = Column(Float, nullable=True)
    longitude      = Column(Float, nullable=True)
    description    = Column(Text, nullable=True)
    image_url      = Column(String, nullable=True)
    image_credit   = Column(String, nullable=True)
    category       = Column(String(100), nullable=True)  # L1 slug
    avg_duration_hours = Column(Float, nullable=True)    # timp mediu vizită
    entry_fee_eur  = Column(Float, nullable=True)
    rating         = Column(Float, nullable=True)
    legacy_tags    = Column(Text, nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    city           = relationship("City", back_populates="attractions")
    tags           = relationship("Tag", secondary=attraction_tags, lazy="select")