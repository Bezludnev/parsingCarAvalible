# app/api/car_details.py - НОВЫЙ API для детальных данных
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.repository.car_repository import CarRepository
from app.schemas.car import CarResponse, CarDetailUpdate
from app.services.scraper_service import ScraperService
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/car-details", tags=["Car Details"])


@router.get("/without-details", response_model=List[CarResponse])
async def get_cars_without_details(
        limit: int = Query(default=20, ge=1, le=100),
        db: AsyncSession = Depends(get_db)
):
    """📋 Получить машины без детальной информации"""
    repo = CarRepository(db)
    cars = await repo.get_cars_without_details(limit)
    return cars


@router.get("/with-details", response_model=List[CarResponse])
async def get_cars_with_details(
        filter_name: Optional[str] = Query(default=None),
        limit: int = Query(default=15, ge=1, le=50),
        db: AsyncSession = Depends(get_db)
):
    """📋 Получить машины с детальной информацией"""
    repo = CarRepository(db)
    cars = await repo.get_cars_with_details(filter_name, limit)
    return cars


@router.post("/parse-details/{car_id}")
async def parse_car_details(
        car_id: int,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db)
):
    """🔍 Запарсить детальную информацию для конкретного автомобиля"""
    repo = CarRepository(db)
    car = await repo.get_by_id(car_id)

    if not car:
        raise HTTPException(status_code=404, detail="Автомобиль не найден")

    if car.details_parsed:
        return {
            "message": "Детали уже парсированы",
            "car_id": car_id,
            "parsed_at": car.details_parsed_at
        }

    # Запускаем парсинг в фоне
    background_tasks.add_task(parse_single_car_details_task, car_id, car.link)

    return {
        "message": "Парсинг деталей запущен в фоне",
        "car_id": car_id,
        "status": "processing"
    }


@router.post("/parse-batch")
async def parse_details_batch(
        background_tasks: BackgroundTasks,
        filter_name: Optional[str] = Query(default=None),
        limit: int = Query(default=10, ge=1, le=30),
        db: AsyncSession = Depends(get_db)
):
    """🔄 Пакетный парсинг деталей для машин без детальной информации"""
    repo = CarRepository(db)

    if filter_name:
        # Получаем машины конкретного фильтра без деталей
        all_cars = await repo.get_cars_by_filter(filter_name, 100)
        cars_without_details = [car for car in all_cars if not car.details_parsed][:limit]
    else:
        cars_without_details = await repo.get_cars_without_details(limit)

    if not cars_without_details:
        return {
            "message": "Нет машин для парсинга деталей",
            "total_cars": 0
        }

    # Запускаем пакетный парсинг в фоне
    background_tasks.add_task(
        parse_batch_details_task,
        [car.id for car in cars_without_details],
        [car.link for car in cars_without_details]
    )

    return {
        "message": f"Пакетный парсинг деталей запущен для {len(cars_without_details)} машин",
        "total_cars": len(cars_without_details),
        "filter_name": filter_name,
        "status": "processing"
    }


@router.get("/search")
async def search_cars_by_characteristics(
        mot_till: Optional[str] = Query(default=None),
        colour: Optional[str] = Query(default=None),
        gearbox: Optional[str] = Query(default=None),
        fuel_type: Optional[str] = Query(default=None),
        condition: Optional[str] = Query(default=None),
        limit: int = Query(default=20, ge=1, le=50),
        db: AsyncSession = Depends(get_db)
):
    """🔎 Поиск машин по характеристикам"""
    repo = CarRepository(db)
    cars = await repo.search_cars_by_characteristics(
        mot_till=mot_till,
        colour=colour,
        gearbox=gearbox,
        fuel_type=fuel_type,
        condition=condition,
        limit=limit
    )

    return {
        "total_found": len(cars),
        "search_criteria": {
            "mot_till": mot_till,
            "colour": colour,
            "gearbox": gearbox,
            "fuel_type": fuel_type,
            "condition": condition
        },
        "cars": cars
    }


@router.get("/stats")
async def get_detailed_stats(db: AsyncSession = Depends(get_db)):
    """📊 Детальная статистика с учетом новых полей"""
    repo = CarRepository(db)
    stats = await repo.get_cars_stats_detailed()

    return {
        "status": "success",
        "statistics": stats
    }


@router.put("/update/{car_id}")
async def update_car_details_manually(
        car_id: int,
        details: CarDetailUpdate,
        db: AsyncSession = Depends(get_db)
):
    """✏️ Ручное обновление детальной информации автомобиля"""
    repo = CarRepository(db)

    updated_car = await repo.update_car_details(car_id, details)
    if not updated_car:
        raise HTTPException(status_code=404, detail="Автомобиль не найден")

    return {
        "message": "Детали автомобиля обновлены",
        "car_id": car_id,
        "updated_at": updated_car.details_parsed_at
    }


# === ФОНОВЫЕ ЗАДАЧИ ===

async def parse_single_car_details_task(car_id: int, car_link: str):
    """Фоновая задача для парсинга деталей одного автомобиля"""
    try:
        logger.info(f"Начинаем парсинг деталей для машины ID {car_id}")

        scraper = ScraperService()
        driver = scraper._create_driver()

        try:
            detail_update = scraper.parse_car_details(driver, car_link)

            # Обновляем в базе данных
            from app.database import async_session
            async with async_session() as session:
                repo = CarRepository(session)
                await repo.update_car_details(car_id, detail_update)

            logger.info(f"✅ Детали успешно парсированы для машины ID {car_id}")

        finally:
            driver.quit()

    except Exception as e:
        logger.error(f"❌ Ошибка парсинга деталей для машины ID {car_id}: {e}")


async def parse_batch_details_task(car_ids: List[int], car_links: List[str]):
    """Фоновая задача для пакетного парсинга деталей"""
    try:
        logger.info(f"Начинаем пакетный парсинг деталей для {len(car_ids)} машин")

        scraper = ScraperService()
        detail_updates = await scraper.scrape_car_details_batch(car_links)

        # Обновляем все машины в базе
        from app.database import async_session
        async with async_session() as session:
            repo = CarRepository(session)

            for car_id, detail_update in zip(car_ids, detail_updates):
                await repo.update_car_details(car_id, detail_update)

        success_count = sum(1 for update in detail_updates if update.details_parsed)
        logger.info(f"✅ Пакетный парсинг завершен: {success_count}/{len(car_ids)} успешно")

    except Exception as e:
        logger.error(f"❌ Ошибка пакетного парсинга деталей: {e}")