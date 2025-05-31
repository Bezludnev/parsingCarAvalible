# app/schemas/car.py - ОБНОВЛЕННЫЕ с детальными полями
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any


class CarBase(BaseModel):
    title: str
    link: str
    price: Optional[str] = None
    brand: str
    year: Optional[int] = None
    mileage: Optional[int] = None
    features: Optional[str] = None
    date_posted: Optional[str] = None
    place: Optional[str] = None
    filter_name: str

    # === НОВЫЕ ДЕТАЛЬНЫЕ ПОЛЯ ===

    # Технические характеристики
    mot_till: Optional[str] = None
    colour: Optional[str] = None
    gearbox: Optional[str] = None
    fuel_type: Optional[str] = None
    engine_size: Optional[str] = None
    doors: Optional[str] = None
    seats: Optional[str] = None

    # Дополнительные характеристики
    condition: Optional[str] = None
    previous_owners: Optional[str] = None
    registration: Optional[str] = None
    import_duty_paid: Optional[str] = None
    roadworthy_certificate: Optional[str] = None

    # Описание и контакты
    description: Optional[str] = None
    seller_type: Optional[str] = None
    contact_info: Optional[str] = None

    # Парсинг деталей
    details_parsed: bool = False

    # Дополнительные характеристики как JSON
    extra_characteristics: Optional[str] = None


class CarCreate(CarBase):
    pass


class CarResponse(CarBase):
    id: int
    is_notified: bool
    created_at: datetime
    details_parsed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CarDetailUpdate(BaseModel):
    """Схема для обновления детальной информации существующей машины"""

    # Технические характеристики
    mot_till: Optional[str] = None
    colour: Optional[str] = None
    gearbox: Optional[str] = None
    fuel_type: Optional[str] = None
    engine_size: Optional[str] = None
    doors: Optional[str] = None
    seats: Optional[str] = None

    # Дополнительные характеристики
    condition: Optional[str] = None
    previous_owners: Optional[str] = None
    registration: Optional[str] = None
    import_duty_paid: Optional[str] = None
    roadworthy_certificate: Optional[str] = None

    # Описание и контакты
    description: Optional[str] = None
    seller_type: Optional[str] = None
    contact_info: Optional[str] = None

    # Дополнительные характеристики
    extra_characteristics: Optional[str] = None

    details_parsed: bool = True