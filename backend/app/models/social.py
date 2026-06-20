from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Friendship(Base):
    __tablename__ = "friendships"
    id = Column(Integer, primary_key=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")  # pending | accepted | declined
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    requester = relationship("User", foreign_keys=[requester_id])
    receiver = relationship("User", foreign_keys=[receiver_id])


class GroupTrip(Base):
    __tablename__ = "group_trips"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)
    nr_zile = Column(Integer, default=5)
    status = Column(String, default="planning")  # planning | confirmed | completed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    members = relationship("GroupTripMember", back_populates="trip")
    creator = relationship("User", foreign_keys=[creator_id])


class GroupTripMember(Base):
    __tablename__ = "group_trip_members"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("group_trips.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    trip = relationship("GroupTrip", back_populates="members")
    user = relationship("User")
