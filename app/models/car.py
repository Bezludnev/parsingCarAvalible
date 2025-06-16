# app/models/car.py
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    link = Column(String(500), unique=True, nullable=False, index=True)
    price = Column(String(100))
    brand = Column(String(50), index=True)
    year = Column(Integer, index=True)
    mileage = Column(Integer, index=True)
    features = Column(Text)
    description = Column(Text)
    date_posted = Column(String(100))
    place = Column(String(200))
    filter_name = Column(String(50), index=True)
    is_notified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    contact_attempts_count = Column(Integer, default=0)
    last_contact_attempt = Column(DateTime)
    seller_response_rate = Column(Float)  # % ответов продавца