# app/models/car.py - ОБНОВЛЕННАЯ с детальными полями
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
    date_posted = Column(String(100))
    place = Column(String(200))
    filter_name = Column(String(50), index=True)
    is_notified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # === НОВЫЕ ДЕТАЛЬНЫЕ ПОЛЯ ===

    # Технические характеристики
    mot_till = Column(String(50))  # MOT до (техосмотр)
    colour = Column(String(50))  # Цвет
    gearbox = Column(String(50))  # Коробка передач
    fuel_type = Column(String(50))  # Тип топлива
    engine_size = Column(String(50))  # Объем двигателя
    doors = Column(String(20))  # Количество дверей
    seats = Column(String(20))  # Количество мест

    # Дополнительные характеристики
    condition = Column(String(50))  # Состояние
    previous_owners = Column(String(20))  # Предыдущие владельцы
    registration = Column(String(100))  # Регистрация
    import_duty_paid = Column(String(20))  # Пошлина оплачена
    roadworthy_certificate = Column(String(20))  # Сертификат техсостояния

    # Описание и контакты
    description = Column(Text)  # Полное описание
    seller_type = Column(String(50))  # Тип продавца (частное лицо/дилер)
    contact_info = Column(Text)  # Контактная информация

    # Детальный парсинг
    details_parsed = Column(Boolean, default=False)  # Флаг парсинга деталей
    details_parsed_at = Column(DateTime)  # Когда парсились детали

    # JSON поле для хранения всех остальных характеристик
    extra_characteristics = Column(Text)  # JSON строка с доп. характеристиками