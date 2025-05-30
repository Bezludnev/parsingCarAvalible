# app/services/analysis_service.py
from typing import List, Dict, Any, Optional
from app.services.openai_service import OpenAIService
from app.repository.car_repository import CarRepository
from app.database import async_session
import logging

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self):
        self.openai_service = OpenAIService()

    async def analyze_cars_by_filter(self, filter_name: str, limit: int = 20) -> Dict[str, Any]:
        """Анализирует машины по фильтру"""
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_cars_by_filter(filter_name, limit)

            if not cars:
                return {
                    "error": f"Нет машин для фильтра {filter_name}",
                    "total_cars_analyzed": 0
                }

            logger.info(f"Анализируем {len(cars)} машин для фильтра {filter_name}")
            analysis = await self.openai_service.analyze_cars(cars)

            # Добавляем метаданные
            analysis["filter_name"] = filter_name
            analysis["analysis_type"] = "by_filter"

            return analysis

    async def analyze_all_recent_cars(self, days: int = 7, limit: int = 30) -> Dict[str, Any]:
        """Анализирует все недавние машины"""
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_recent_cars(days, limit)

            if not cars:
                return {
                    "error": f"Нет машин за последние {days} дней",
                    "total_cars_analyzed": 0
                }

            logger.info(f"Анализируем {len(cars)} машин за {days} дней")
            analysis = await self.openai_service.analyze_cars(cars)

            analysis["days_period"] = days
            analysis["analysis_type"] = "recent_cars"

            return analysis

    async def compare_specific_cars(self, car_ids: List[int]) -> Dict[str, Any]:
        """Сравнивает конкретные машины по ID"""
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_cars_by_ids(car_ids)

            if not cars:
                return {
                    "error": "Машины не найдены",
                    "total_cars_analyzed": 0
                }

            logger.info(f"Сравниваем {len(cars)} конкретных машин")
            analysis = await self.openai_service.analyze_cars(cars)

            analysis["compared_car_ids"] = car_ids
            analysis["analysis_type"] = "comparison"

            return analysis

    async def get_brand_analysis(self, brand: str, limit: int = 15) -> Dict[str, Any]:
        """Анализ по конкретной марке"""
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_cars_by_brand(brand, limit)

            if not cars:
                return {
                    "error": f"Нет машин марки {brand}",
                    "total_cars_analyzed": 0
                }

            logger.info(f"Анализируем {len(cars)} машин марки {brand}")
            analysis = await self.openai_service.analyze_cars(cars)

            analysis["brand"] = brand
            analysis["analysis_type"] = "by_brand"

            return analysis