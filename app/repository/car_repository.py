# app/repository/car_repository.py - ОБНОВЛЕННЫЙ с детальными полями
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func, update
from app.models.car import Car
from app.schemas.car import CarCreate, CarDetailUpdate
from typing import List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class CarRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_link(self, link: str) -> Optional[Car]:
        result = await self.session.execute(
            select(Car).where(Car.link == link)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, car_id: int) -> Optional[Car]:
        return await self.session.get(Car, car_id)

    async def create(self, car_data: CarCreate) -> Car:
        car = Car(**car_data.dict())
        self.session.add(car)
        await self.session.commit()
        await self.session.refresh(car)
        return car

    async def get_unnotified_cars(self) -> List[Car]:
        result = await self.session.execute(
            select(Car).where(Car.is_notified == False)
        )
        return result.scalars().all()

    async def mark_as_notified(self, car_id: int):
        car = await self.session.get(Car, car_id)
        if car:
            car.is_notified = True
            await self.session.commit()

    async def get_cars_by_filter(self, filter_name: str, limit: int = 10) -> List[Car]:
        result = await self.session.execute(
            select(Car)
            .where(Car.filter_name == filter_name)
            .order_by(Car.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    # === НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С ДЕТАЛЬНЫМИ ДАННЫМИ ===

    async def update_car_details(self, car_id: int, details: CarDetailUpdate) -> Optional[Car]:
        """🔄 Обновляет детальную информацию автомобиля"""
        try:
            car = await self.session.get(Car, car_id)
            if not car:
                return None

            # Обновляем все поля из детальных данных
            update_data = details.dict(exclude_unset=True)
            update_data['details_parsed_at'] = datetime.now()

            for field, value in update_data.items():
                if hasattr(car, field) and value is not None:
                    setattr(car, field, value)

            await self.session.commit()
            await self.session.refresh(car)

            logger.info(f"✅ Детали обновлены для машины ID {car_id}")
            return car

        except Exception as e:
            logger.error(f"❌ Ошибка обновления деталей для машины {car_id}: {e}")
            await self.session.rollback()
            return None

    async def get_cars_without_details(self, limit: int = 20) -> List[Car]:
        """🔍 Получает машины без детальной информации"""
        result = await self.session.execute(
            select(Car)
            .where(Car.details_parsed == False)
            .order_by(Car.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_cars_with_details(self, filter_name: str = None, limit: int = 15) -> List[Car]:
        """📋 Получает машины с детальной информацией"""
        query = select(Car).where(Car.details_parsed == True)

        if filter_name:
            query = query.where(Car.filter_name == filter_name)

        query = query.order_by(Car.created_at.desc()).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def search_cars_by_characteristics(self,
                                             mot_till: str = None,
                                             colour: str = None,
                                             gearbox: str = None,
                                             fuel_type: str = None,
                                             condition: str = None,
                                             limit: int = 20) -> List[Car]:
        """🔎 Поиск машин по характеристикам"""

        query = select(Car).where(Car.details_parsed == True)

        if mot_till:
            query = query.where(Car.mot_till.ilike(f"%{mot_till}%"))
        if colour:
            query = query.where(Car.colour.ilike(f"%{colour}%"))
        if gearbox:
            query = query.where(Car.gearbox.ilike(f"%{gearbox}%"))
        if fuel_type:
            query = query.where(Car.fuel_type.ilike(f"%{fuel_type}%"))
        if condition:
            query = query.where(Car.condition.ilike(f"%{condition}%"))

        query = query.order_by(Car.created_at.desc()).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_cars_stats_detailed(self) -> dict:
        """📊 Детальная статистика с учетом новых полей"""

        # Базовые статистики
        total_result = await self.session.execute(
            select(func.count(Car.id).label('total'))
        )
        total_cars = total_result.scalar()

        # Статистика парсинга деталей
        details_result = await self.session.execute(
            select(func.count(Car.id).label('with_details'))
            .where(Car.details_parsed == True)
        )
        cars_with_details = details_result.scalar()

        # Статистика по характеристикам
        characteristics_stats = {}

        # Статистика по типам топлива
        fuel_result = await self.session.execute(
            select(Car.fuel_type, func.count(Car.id).label('count'))
            .where(Car.fuel_type.isnot(None))
            .group_by(Car.fuel_type)
        )
        characteristics_stats['fuel_types'] = dict(fuel_result.fetchall())

        # Статистика по коробкам передач
        gearbox_result = await self.session.execute(
            select(Car.gearbox, func.count(Car.id).label('count'))
            .where(Car.gearbox.isnot(None))
            .group_by(Car.gearbox)
        )
        characteristics_stats['gearboxes'] = dict(gearbox_result.fetchall())

        # Статистика по цветам
        colour_result = await self.session.execute(
            select(Car.colour, func.count(Car.id).label('count'))
            .where(Car.colour.isnot(None))
            .group_by(Car.colour)
            .limit(10)  # Топ 10 цветов
        )
        characteristics_stats['top_colours'] = dict(colour_result.fetchall())

        return {
            'total_cars': total_cars,
            'cars_with_details': cars_with_details,
            'detail_parsing_rate': round((cars_with_details / total_cars * 100), 1) if total_cars > 0 else 0,
            'characteristics_stats': characteristics_stats
        }

    # Существующие методы
    async def get_recent_cars(self, days: int = 7, limit: int = 30) -> List[Car]:
        """Получает машины за последние N дней"""
        cutoff_date = datetime.now() - timedelta(days=days)
        result = await self.session.execute(
            select(Car)
            .where(Car.created_at >= cutoff_date)
            .order_by(Car.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_cars_by_ids(self, car_ids: List[int]) -> List[Car]:
        """Получает машины по списку ID"""
        result = await self.session.execute(
            select(Car).where(Car.id.in_(car_ids))
        )
        return result.scalars().all()

    async def get_cars_by_brand(self, brand: str, limit: int = 15) -> List[Car]:
        """Получает машины по марке"""
        result = await self.session.execute(
            select(Car)
            .where(Car.brand.ilike(f"%{brand}%"))
            .order_by(Car.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_price_statistics(self, filter_name: str = None) -> dict:
        """Статистика по ценам"""
        query = select(
            func.count(Car.id).label('total'),
            func.avg(Car.year).label('avg_year'),
            func.avg(Car.mileage).label('avg_mileage')
        )

        if filter_name:
            query = query.where(Car.filter_name == filter_name)

        result = await self.session.execute(query)
        stats = result.first()


