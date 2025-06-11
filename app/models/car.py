# app/models/car.py - с отслеживанием изменений
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

    # 🆕 НОВЫЕ ПОЛЯ для отслеживания изменений
    previous_price = Column(String(100))  # Предыдущая цена
    previous_description = Column(Text)  # Предыдущее описание
    last_checked_at = Column(DateTime)  # Когда последний раз проверяли
    price_changed_at = Column(DateTime)  # Когда изменилась цена
    description_changed_at = Column(DateTime)  # Когда изменилось описание

    # Счетчики изменений
    price_changes_count = Column(Integer, default=0)  # Сколько раз менялась цена
    description_changes_count = Column(Integer, default=0)  # Сколько раз менялось описание