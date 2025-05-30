# app/api/cars.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.repository.car_repository import CarRepository
from app.schemas.car import CarResponse
from app.services.monitor_service import MonitorService
from typing import List

router = APIRouter(prefix="/cars", tags=["cars"])

@router.get("/", response_model=List[CarResponse])
async def get_cars(
    filter_name: str = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    repo = CarRepository(db)
    if filter_name:
        cars = await repo.get_cars_by_filter(filter_name, limit)
    else:
        # Implement get_all method if needed
        raise HTTPException(400, "filter_name is required")
    return cars

@router.post("/check-now")
async def trigger_check():
    """Ручной запуск проверки новых объявлений"""
    monitor = MonitorService()
    await monitor.check_new_cars()
    return {"message": "Проверка запущена"}
