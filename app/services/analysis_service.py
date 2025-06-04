# app/services/analysis_service.py - ОБНОВЛЕННАЯ с quick insights
from typing import List, Dict, Any, Optional
from app.services.openai_service import OpenAIService
from app.repository.car_repository import CarRepository
from app.database import async_session
import logging
import re

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
                    "success": False,
                    "error": f"Нет машин для фильтра {filter_name}",
                    "total_cars_analyzed": 0
                }

            logger.info(f"Анализируем {len(cars)} машин для фильтра {filter_name}")
            analysis = await self.openai_service.analyze_cars(cars)

            # Добавляем метаданные
            analysis["filter_name"] = filter_name
            analysis["analysis_type"] = "by_filter"
            analysis["success"] = True

            return analysis

    async def analyze_recent_cars(self, days: int = 7, limit: int = 30) -> Dict[str, Any]:
        """Анализирует все недавние машины"""
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_recent_cars(days, limit)

            if not cars:
                return {
                    "success": False,
                    "error": f"Нет машин за последние {days} дней",
                    "total_cars_analyzed": 0
                }

            logger.info(f"Анализируем {len(cars)} машин за {days} дней")
            analysis = await self.openai_service.analyze_cars(cars)

            analysis["days_period"] = days
            analysis["analysis_type"] = "recent_cars"
            analysis["success"] = True

            return analysis

    async def compare_specific_cars(self, car_ids: List[int]) -> Dict[str, Any]:
        """Сравнивает конкретные машины по ID"""
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_cars_by_ids(car_ids)

            if not cars:
                return {
                    "success": False,
                    "error": "Машины не найдены",
                    "total_cars_analyzed": 0
                }

            logger.info(f"Сравниваем {len(cars)} конкретных машин")
            analysis = await self.openai_service.analyze_cars(cars)

            analysis["compared_car_ids"] = car_ids
            analysis["analysis_type"] = "comparison"
            analysis["success"] = True

            return analysis

    async def get_brand_analysis(self, brand: str, limit: int = 15) -> Dict[str, Any]:
        """Анализ по конкретной марке"""
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_cars_by_brand(brand, limit)

            if not cars:
                return {
                    "success": False,
                    "error": f"Нет машин марки {brand}",
                    "total_cars_analyzed": 0
                }

            logger.info(f"Анализируем {len(cars)} машин марки {brand}")
            analysis = await self.openai_service.analyze_cars(cars)

            analysis["brand"] = brand
            analysis["analysis_type"] = "by_brand"
            analysis["success"] = True

            return analysis

    async def get_quick_insight(self, filter_name: str, limit: int = 5) -> Dict[str, Any]:
        """🚀 Быстрый анализ для мониторинга (без детального разбора)"""
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_cars_by_filter(filter_name, limit)

            if not cars:
                return {
                    "success": False,
                    "error": f"Нет машин для {filter_name}",
                    "filter_name": filter_name,
                    "total_cars": 0
                }

            try:
                logger.info(f"Быстрый анализ {len(cars)} машин для {filter_name}")

                # Используем быстрый метод OpenAI service
                quick_rec = await self.openai_service.get_quick_recommendation(cars)

                # Пытаемся извлечь номер рекомендованного автомобиля из текста
                recommended_link = None
                match = re.search(r"#(\d+)", quick_rec)
                if match:
                    try:
                        idx = int(match.group(1)) - 1
                        if 0 <= idx < len(cars):
                            recommended_link = cars[idx].link
                    except Exception:
                        recommended_link = None

                return {
                    "success": True,
                    "filter_name": filter_name,
                    "total_cars": len(cars),
                    "quick_recommendation": quick_rec,
                    "recommended_link": recommended_link,
                    "analysis_type": "quick_insight"
                }

            except Exception as e:
                logger.error(f"Ошибка быстрого анализа {filter_name}: {e}")
                return {
                    "success": False,
                    "error": f"Ошибка анализа: {str(e)}",
                    "filter_name": filter_name,
                    "total_cars": len(cars)
                }

    async def get_filter_statistics(self, filter_name: str) -> Dict[str, Any]:
        """📊 Статистика по фильтру"""
        async with async_session() as session:
            repo = CarRepository(session)

            stats = await repo.get_price_statistics(filter_name)
            recent_cars = await repo.get_recent_cars(7, 50)  # За неделю
            filter_cars = [car for car in recent_cars if car.filter_name == filter_name]

            return {
                "filter_name": filter_name,
                "total_cars": stats.get("total_cars", 0),
                "avg_year": stats.get("avg_year"),
                "avg_mileage": stats.get("avg_mileage"),
                "recent_week": len(filter_cars),
                "cars_per_day": round(len(filter_cars) / 7, 1) if filter_cars else 0
            }

    async def batch_quick_analysis(self, filter_names: List[str]) -> List[Dict[str, Any]]:
        """📦 Пакетный быстрый анализ нескольких фильтров"""
        results = []

        for filter_name in filter_names:
            try:
                result = await self.get_quick_insight(filter_name, 8)
                results.append(result)

            except Exception as e:
                logger.error(f"Ошибка пакетного анализа {filter_name}: {e}")
                results.append({
                    "success": False,
                    "filter_name": filter_name,
                    "error": str(e),
                    "total_cars": 0
                })

        return results