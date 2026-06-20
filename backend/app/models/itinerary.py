from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, JSON, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class ItineraryRating(Base):
    __tablename__ = "itinerary_ratings"
    id          = Column(Integer, primary_key=True, index=True)
    plan_id     = Column(Integer, ForeignKey("itinerary_plans.id"), nullable=False, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rating      = Column(Integer, nullable=False)           # 1-5
    aspects     = Column(JSON, nullable=True, default=list) # ["wrong_vibe", "too_many_stops", ...]
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

class ItineraryPlan(Base):
    __tablename__ = "itinerary_plans"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False, index=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)
    nr_zile = Column(Integer, nullable=False)
    is_saved = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    group_trip_id = Column(Integer, ForeignKey('group_trips.id'), nullable=True)
    source = Column(String, default='auto')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    days = relationship("ItineraryDay", back_populates="plan", cascade="all, delete-orphan")

class ItineraryDay(Base):
    __tablename__ = "itinerary_days"
    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("itinerary_plans.id"), nullable=False)
    day_number = Column(Integer, nullable=False)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=False)
    attraction_ids = Column(JSON, nullable=False, default=list)  # [int]
    plan = relationship("ItineraryPlan", back_populates="days")