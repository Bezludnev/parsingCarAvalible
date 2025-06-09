# app/services/monitor_service.py - ОПТИМИЗИРОВАННАЯ версия без автоматического AI
from app.services.scraper_service import ScraperService
from app.services.telegram_service import TelegramService
from app.services.analysis_service import AnalysisService
from app.repository.car_repository import CarRepository
from app.database import async_session
from app.config import settings
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class MonitorService:
    def __init__(self):
        self.scraper = ScraperService()
        self.telegram = TelegramService()
        self.analysis = AnalysisService()

    async def _is_urgent(self, text: str) -> bool:
        """Проверка текста на признаки срочной продажи через AI"""
        if not text:
            return False
        # Быстрый ключевой фильтр
        keywords = [
            "срочно", "urgent", "быстро", "price drop", "недорого", "must sell"
        ]
        text_lower = text.lower()
        if any(k in text_lower for k in keywords):
            return True

        # AI анализ только для важных случаев
        try:
            return await self.analysis.openai_service.detect_urgent_sale(text)
        except Exception as e:
            logger.error(f"AI urgent detection error: {e}")
            return False

    async def _process_filter(self, filter_name: str, repo: CarRepository) -> int:
        """Скрапинг и обработка одного фильтра с оптимизацией"""
        try:
            filter_config = settings.car_filters.get(filter_name, {})
            is_urgent_filter = filter_config.get("urgent_mode", False)

            # Получаем существующие ссылки для этого фильтра
            existing_links = await repo.get_existing_links_by_filter(filter_name)
            logger.info(f"📋 {filter_name}: {len(existing_links)} существующих ссылок в базе")

            # Передаем existing_links в scraper для оптимизации
            cars = await self.scraper.scrape_cars(filter_name, existing_links)
            logger.info(f"{'🔥' if is_urgent_filter else '📊'} "
                        f"Найдено {len(cars)} НОВЫХ объявлений для {filter_name}")

            new_cars_count = 0
            for car_data in cars:
                # Дополнительная проверка на всякий случай
                existing_car = await repo.get_by_link(car_data.link)
                if not existing_car:
                    new_car = await repo.create(car_data)
                    logger.info(f"✅ Новая машина: {new_car.title}")

                    # Проверяем urgent статус
                    urgent = await self._is_urgent(new_car.description or "")

                    # Отправляем уведомление
                    await self.telegram.send_new_car_notification(
                        new_car,
                        urgent=urgent or is_urgent_filter,
                        urgent_filter=is_urgent_filter
                    )

                    await repo.mark_as_notified(new_car.id)
                    new_cars_count += 1

            return new_cars_count

        except Exception as e:
            logger.error(f"❌ Ошибка при обработке фильтра {filter_name}: {e}")
            return 0

    async def check_new_cars(self):
        """Основная функция для проверки новых машин БЕЗ автоматического AI анализа"""
        logger.info("🔍 Начинаем проверку новых объявлений...")

        new_cars_found = {}
        urgent_filters_stats = {}

        async with async_session() as session:
            repo = CarRepository(session)

            # Разделяем фильтры на обычные и urgent
            regular_filters = []
            urgent_filters = []

            for filter_name, config in settings.car_filters.items():
                if config.get("urgent_mode", False):
                    urgent_filters.append(filter_name)
                else:
                    regular_filters.append(filter_name)

            # Сначала обрабатываем URGENT фильтры (приоритет)
            if urgent_filters:
                logger.info(f"🔥 Обрабатываем urgent фильтры: {urgent_filters}")

                for filter_name in urgent_filters:
                    count = await self._process_filter(filter_name, repo)
                    new_cars_found[filter_name] = count
                    urgent_filters_stats[filter_name] = count

                # Если в urgent найдены машины - отправляем сводку
                urgent_total = sum(urgent_filters_stats.values())
                if urgent_total > 0:
                    await self.telegram.send_urgent_summary(urgent_filters_stats)

            # Затем обрабатываем обычные фильтры
            logger.info(f"📊 Обрабатываем обычные фильтры: {regular_filters}")

            for filter_name in regular_filters:
                count = await self._process_filter(filter_name, repo)
                new_cars_found[filter_name] = count

        # Простая сводка без AI анализа
        total_new_cars = sum(new_cars_found.values())

        if total_new_cars > 0:
            logger.info(f"✅ Найдено {total_new_cars} новых машин")

            # Краткая статистика в лог
            for filter_name, count in new_cars_found.items():
                if count > 0:
                    urgent_mark = "🔥" if filter_name in urgent_filters_stats else "📊"
                    logger.info(f"  {urgent_mark} {filter_name}: {count} машин")
        else:
            logger.info("😴 Новых машин не найдено")

        logger.info("✅ Проверка завершена (AI анализ отключен)")

    async def run_urgent_check_only(self):
        """🔥 Отдельная проверка только urgent фильтров"""
        logger.info("🔥 Проверка только URGENT фильтров...")

        urgent_found = {}

        async with async_session() as session:
            repo = CarRepository(session)

            urgent_filters = [name for name, config in settings.car_filters.items()
                              if config.get("urgent_mode", False)]

            for filter_name in urgent_filters:
                count = await self._process_filter(filter_name, repo)
                urgent_found[filter_name] = count

        total_urgent = sum(urgent_found.values())

        if total_urgent > 0:
            logger.info(f"🔥 Найдено {total_urgent} urgent машин")
            await self.telegram.send_urgent_summary(urgent_found)

            # AI анализ для urgent (опционально)
            for filter_name, count in urgent_found.items():
                if count > 0:
                    try:
                        quick_result = await self.analysis.get_quick_insight(filter_name)
                        if quick_result.get("success"):
                            await self.telegram.send_quick_analysis_notification(
                                quick_result, urgent_mode=True
                            )
                    except Exception as e:
                        logger.error(f"❌ Urgent AI анализ ошибка {filter_name}: {e}")
        else:
            logger.info("😴 Urgent машин не найдено")

    async def run_manual_ai_analysis(self, filter_name: str = None):
        """🔧 Ручной запуск AI анализа с поддержкой urgent режима"""
        if filter_name:
            # Анализ конкретного фильтра
            logger.info(f"🔧 Ручной AI анализ для {filter_name}")

            filter_config = settings.car_filters.get(filter_name, {})
            is_urgent = filter_config.get("urgent_mode", False)

            try:
                result = await self.analysis.analyze_cars_by_filter(filter_name, 15)

                if result.get("success"):
                    await self.telegram.send_ai_analysis_report(result, urgent_mode=is_urgent)
                    return {
                        "status": "success",
                        "filter": filter_name,
                        "urgent_mode": is_urgent,
                        "cars_analyzed": result.get("total_cars_analyzed", 0)
                    }
                else:
                    return {"status": "error", "filter": filter_name, "error": result.get("error")}

            except Exception as e:
                logger.error(f"❌ Ошибка ручного анализа {filter_name}: {e}")
                return {"status": "error", "filter": filter_name, "error": str(e)}

        else:
            # Анализ всех фильтров
            logger.info("🔧 Ручной AI анализ всех фильтров")
            results = []

            for filter_name, config in settings.car_filters.items():
                is_urgent = config.get("urgent_mode", False)

                try:
                    quick_result = await self.analysis.get_quick_insight(filter_name)

                    if quick_result.get("success") and quick_result.get("total_cars", 0) >= 2:
                        full_result = await self.analysis.analyze_cars_by_filter(filter_name, 10)

                        if full_result.get("success"):
                            await self.telegram.send_ai_analysis_report(
                                full_result, urgent_mode=is_urgent
                            )
                            results.append({
                                "filter": filter_name,
                                "status": "success",
                                "urgent_mode": is_urgent,
                                "cars": full_result.get("total_cars_analyzed", 0)
                            })
                        else:
                            results.append({
                                "filter": filter_name,
                                "status": "error",
                                "urgent_mode": is_urgent,
                                "error": full_result.get("error")
                            })
                    else:
                        results.append({
                            "filter": filter_name,
                            "status": "skipped",
                            "urgent_mode": is_urgent,
                            "reason": "insufficient_cars"
                        })

                except Exception as e:
                    logger.error(f"❌ Ошибка анализа {filter_name}: {e}")
                    results.append({
                        "filter": filter_name,
                        "status": "error",
                        "urgent_mode": is_urgent,
                        "error": str(e)
                    })

            return {"status": "completed", "results": results}

    async def get_filters_status(self) -> Dict:
        """📊 Статус всех фильтров с разделением на обычные/urgent"""
        regular_filters = []
        urgent_filters = []

        for name, config in settings.car_filters.items():
            filter_info = {
                "name": name,
                "brand": config["brand"],
                "min_year": config["min_year"],
                "max_mileage": config["max_mileage"]
            }

            if config.get("urgent_mode", False):
                urgent_filters.append(filter_info)
            else:
                regular_filters.append(filter_info)

        return {
            "total_filters": len(settings.car_filters),
            "regular_filters": regular_filters,
            "urgent_filters": urgent_filters,
            "urgent_count": len(urgent_filters),
            "regular_count": len(regular_filters)
        }