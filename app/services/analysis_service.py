# app/services/analysis_service.py - ОПТИМИЗИРОВАННАЯ для анализа всей базы
from typing import List, Dict, Any, Optional
from app.services.openai_service import OpenAIService
from app.repository.car_repository import CarRepository
from app.database import async_session
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self):
        self.openai_service = OpenAIService()

    async def analyze_full_database(self, min_cars_per_brand: int = 5) -> Dict[str, Any]:
        """🎯 ОСНОВНОЙ МЕТОД: Анализ всей базы данных одним запросом"""
        async with async_session() as session:
            repo = CarRepository(session)

            # Получаем все машины из базы
            all_cars = await repo.get_all_cars_for_analysis()

            if len(all_cars) < 10:
                return {
                    "success": False,
                    "error": f"Недостаточно машин в базе: {len(all_cars)}. Минимум: 10",
                    "total_cars_analyzed": len(all_cars)
                }

            # Группируем по брендам для статистики
            brands_stats = self._group_cars_by_brands(all_cars)

            # Фильтруем бренды с минимальным количеством машин
            significant_brands = {
                brand: cars for brand, cars in brands_stats.items()
                if len(cars) >= min_cars_per_brand
            }

            logger.info(f"🎯 Полный анализ базы: {len(all_cars)} машин, "
                        f"{len(significant_brands)} значимых брендов")

            try:
                # Один большой AI анализ всей базы
                analysis = await self.openai_service.analyze_full_market(
                    all_cars, significant_brands
                )

                # Добавляем метаданные
                analysis.update({
                    "analysis_type": "full_database",
                    "success": True,
                    "total_cars_analyzed": len(all_cars),
                    "analyzed_brands": list(significant_brands.keys()),
                    "brands_statistics": {
                        brand: len(cars) for brand, cars in significant_brands.items()
                    },
                    "analysis_timestamp": datetime.now().isoformat(),
                    "database_snapshot": True
                })

                return analysis

            except Exception as e:
                logger.error(f"❌ Ошибка полного анализа базы: {e}")
                return {
                    "success": False,
                    "error": f"Ошибка AI анализа: {str(e)}",
                    "total_cars_analyzed": len(all_cars)
                }

    async def analyze_recent_market_trends(self, days: int = 14) -> Dict[str, Any]:
        """📈 Анализ трендов за последние N дней на основе всей базы"""
        async with async_session() as session:
            repo = CarRepository(session)

            # Получаем все машины с группировкой по дням
            all_cars = await repo.get_all_cars_for_analysis()
            recent_cars = await repo.get_recent_cars(days, 500)

            if len(all_cars) < 20:
                return {
                    "success": False,
                    "error": "Недостаточно данных для анализа трендов",
                    "total_cars_analyzed": len(all_cars)
                }

            logger.info(f"📈 Анализ трендов: {len(all_cars)} всего, "
                        f"{len(recent_cars)} за {days} дней")

            try:
                # AI анализ трендов
                analysis = await self.openai_service.analyze_market_trends(
                    all_cars, recent_cars, days
                )

                analysis.update({
                    "analysis_type": "market_trends",
                    "success": True,
                    "total_cars_analyzed": len(all_cars),
                    "recent_cars_count": len(recent_cars),
                    "trends_period_days": days,
                    "analysis_timestamp": datetime.now().isoformat()
                })

                return analysis

            except Exception as e:
                logger.error(f"❌ Ошибка анализа трендов: {e}")
                return {
                    "success": False,
                    "error": f"Ошибка анализа трендов: {str(e)}",
                    "total_cars_analyzed": len(all_cars)
                }

    async def get_market_insights_summary(self) -> Dict[str, Any]:
        """⚡ Быстрая сводка по всему рынку (без детального анализа)"""
        async with async_session() as session:
            repo = CarRepository(session)

            # Статистика по всей базе
            total_stats = await repo.get_global_statistics()
            recent_stats = await repo.get_recent_statistics(7)
            brands_breakdown = await repo.get_brands_breakdown()

            return {
                "success": True,
                "analysis_type": "market_summary",
                "total_cars_in_db": total_stats.get("total_cars", 0),
                "avg_price": total_stats.get("avg_price"),
                "avg_year": total_stats.get("avg_year"),
                "avg_mileage": total_stats.get("avg_mileage"),
                "recent_week_additions": recent_stats.get("new_cars_count", 0),
                "brands_breakdown": brands_breakdown,
                "most_popular_brand": max(brands_breakdown.items(), key=lambda x: x[1])[
                    0] if brands_breakdown else None,
                "analysis_timestamp": datetime.now().isoformat()
            }

    def _group_cars_by_brands(self, cars: List) -> Dict[str, List]:
        """Группирует машины по брендам"""
        brands = {}
        for car in cars:
            brand = car.brand or "Unknown"
            if brand not in brands:
                brands[brand] = []
            brands[brand].append(car)
        return brands

    # LEGACY методы для backward compatibility
    async def analyze_cars_by_filter(self, filter_name: str, limit: int = 20) -> Dict[str, Any]:
        """Legacy: анализ по фильтру (теперь берет данные из базы)"""
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_cars_by_filter(filter_name, limit)

            if not cars:
                return {
                    "success": False,
                    "error": f"Нет машин для фильтра {filter_name}",
                    "total_cars_analyzed": 0
                }

            logger.info(f"📊 Legacy анализ фильтра {filter_name}: {len(cars)} машин")

            # Используем базовый метод OpenAI
            analysis = await self.openai_service.analyze_cars(cars)
            analysis.update({
                "filter_name": filter_name,
                "analysis_type": "by_filter_legacy",
                "success": True
            })

            return analysis

    async def compare_specific_cars(self, car_ids: List[int]) -> Dict[str, Any]:
        """Сравнение конкретных машин по ID"""
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_cars_by_ids(car_ids)

            if not cars:
                return {
                    "success": False,
                    "error": "Машины не найдены",
                    "total_cars_analyzed": 0
                }

            logger.info(f"🆚 Сравнение {len(cars)} конкретных машин")
            analysis = await self.openai_service.analyze_cars(cars)
            analysis.update({
                "compared_car_ids": car_ids,
                "analysis_type": "comparison",
                "success": True
            })

            return analysis

    async def get_quick_insight(self, filter_name: str, limit: int = 5) -> Dict[str, Any]:
        """🚀 Быстрый insight (без полного анализа)"""
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
                quick_rec = await self.openai_service.get_quick_recommendation(cars)

                # Ищем рекомендованную машину
                import re
                recommended_link = None
                match = re.search(r"#(\d+)", quick_rec)
                if match:
                    try:
                        idx = int(match.group(1)) - 1
                        if 0 <= idx < len(cars):
                            recommended_link = cars[idx].link
                    except Exception:
                        pass

                return {
                    "success": True,
                    "filter_name": filter_name,
                    "total_cars": len(cars),
                    "quick_recommendation": quick_rec,
                    "recommended_link": recommended_link,
                    "analysis_type": "quick_insight"
                }

            except Exception as e:
                logger.error(f"❌ Ошибка быстрого анализа {filter_name}: {e}")
                return {
                    "success": False,
                    "error": f"Ошибка анализа: {str(e)}",
                    "filter_name": filter_name,
                    "total_cars": len(cars)
                }