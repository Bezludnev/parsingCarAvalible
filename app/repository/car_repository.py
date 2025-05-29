
# app/repository/car_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.car import Car
from app.schemas.car import CarCreate
from typing import List, Optional


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

