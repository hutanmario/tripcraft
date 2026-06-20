from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date, datetime


class ItineraryStopCreate(BaseModel):
    destination_id: int
    order: int
    days_spent: int = 1
    estimated_cost: Optional[float] = None
    notes: Optional[str] = None


class ItineraryStopResponse(BaseModel):
    id: int
    destination_id: int
    order: int
    days_spent: int
    estimated_cost: Optional[float]
    notes: Optional[str]
    destination_name: Optional[str] = None
    destination_country: Optional[str] = None
    destination_image_url: Optional[str] = None
    destination_lat: Optional[float] = None
    destination_lon: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ItineraryCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_public: bool = False
    stops: List[ItineraryStopCreate]


class ItineraryUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_public: Optional[bool] = None
    stops: Optional[List[ItineraryStopCreate]] = None


class ItineraryResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    total_cost: Optional[float]
    total_days: Optional[int]
    is_public: bool
    created_at: datetime
    stops: List[ItineraryStopResponse]

    model_config = ConfigDict(from_attributes=True)


class ItineraryListItem(BaseModel):
    id: int
    title: str
    description: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    total_cost: Optional[float]
    total_days: Optional[int]
    is_public: bool
    created_at: datetime
    stop_count: int

    model_config = ConfigDict(from_attributes=True)