
# app/schemas/car.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CarBase(BaseModel):
    title: str
    link: str
    price: Optional[str] = None
    brand: str
    year: Optional[int] = None
    mileage: Optional[int] = None
    features: Optional[str] = None
    description: Optional[str] = None
    date_posted: Optional[str] = None
    place: Optional[str] = None
    filter_name: str


class CarCreate(CarBase):
    pass


class CarResponse(CarBase):
    id: int
    is_notified: bool
    created_at: datetime

    class Config:
        from_attributes = True