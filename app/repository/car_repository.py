# app/repository/car_repository.py (updated)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from app.models.car import Car
from app.schemas.car import CarCreate
from typing import List, Optional
from datetime import datetime, timedelta


class CarRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_link(self, link: str) -> Optional[Car]:
        result = await self.session.execute(
            select(Car).where(Car.link == link)
        )
        return result.scalar_one_or_none()

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

    # Новые методы для анализа
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

        return {
            'total_cars': stats.total,
            'avg_year': round(stats.avg_year, 1) if stats.avg_year else None,
            'avg_mileage': round(stats.avg_mileage, 1) if stats.avg_mileage else None
        }