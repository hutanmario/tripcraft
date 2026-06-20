import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base, engine
from app.models.social import Friendship, GroupTrip, GroupTripMember

Base.metadata.create_all(bind=engine, tables=[
    Friendship.__table__,
    GroupTrip.__table__,
    GroupTripMember.__table__,
])
print("Social tables created!")
