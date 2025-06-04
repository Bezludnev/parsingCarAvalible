# app/services/monitor_service.py - ОБНОВЛЕННАЯ с urgent поддержкой
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
        # Сначала быстрый ключевой фильтр
        keywords = [
            "срочно", "urgent", "быстро", "price drop", "недорого", "must sell"
        ]
        text_lower = text.lower()
        if any(k in text_lower for k in keywords):
            return True

        # Если ключевых слов нет, используем AI определение
        try:
            return await self.analysis.openai_service.detect_urgent_sale(text)
        except Exception as e:
            logger.error(f"AI urgent detection error: {e}")
            return False

    async def _process_filter(self, filter_name: str, repo: CarRepository) -> int:
        """Скрапинг и обработка одного фильтра"""
        try:
            filter_config = settings.car_filters.get(filter_name, {})
            is_urgent_filter = filter_config.get("urgent_mode", False)

            cars = await self.scraper.scrape_cars(filter_name)
            logger.info(f"{'🔥' if is_urgent_filter else '📊'} "
                        f"Найдено {len(cars)} объявлений для {filter_name}")

            new_cars_count = 0
            for car_data in cars:
                existing_car = await repo.get_by_link(car_data.link)
                if not existing_car:
                    new_car = await repo.create(car_data)
                    logger.info(f"✅ Новая машина: {new_car.title}")

                    # Проверяем urgent статус
                    urgent = await self._is_urgent(new_car.description or "")

                    # Отправляем уведомление с учетом urgent режима
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
        """Основная функция для проверки новых машин + AI анализ"""
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

        # AI анализ если найдены новые машины
        total_new_cars = sum(new_cars_found.values())

        if total_new_cars > 0:
            logger.info(f"🤖 Найдено {total_new_cars} новых машин, запускаем AI анализ...")
            await self._run_ai_analysis_for_new_cars(new_cars_found, urgent_filters_stats)
        else:
            logger.info("😴 Новых машин не найдено")

        logger.info("✅ Проверка завершена")

    async def _run_ai_analysis_for_new_cars(self, new_cars_found: dict, urgent_stats: dict):
        """Запускает AI анализ для фильтров с новыми машинами"""
        analysis_summaries = []

        for filter_name, new_count in new_cars_found.items():
            if new_count > 0:
                try:
                    filter_config = settings.car_filters.get(filter_name, {})
                    is_urgent_filter = filter_config.get("urgent_mode", False)

                    logger.info(f"🔍 AI анализ для {filter_name} "
                                f"({'URGENT' if is_urgent_filter else 'обычный'}) "
                                f"- {new_count} новых машин")

                    # Быстрый анализ
                    quick_result = await self.analysis.get_quick_insight(filter_name)

                    if quick_result.get("success"):
                        # Отправляем с пометкой urgent если это urgent фильтр
                        await self.telegram.send_quick_analysis_notification(
                            quick_result,
                            urgent_mode=is_urgent_filter
                        )
                        analysis_summaries.append(quick_result)

                        # Полный анализ только если достаточно машин
                        threshold = 2 if is_urgent_filter else 3

                        if quick_result.get("total_cars", 0) >= threshold:
                            full_result = await self.analysis.analyze_cars_by_filter(filter_name, 15)

                            if full_result.get("success"):
                                await self.telegram.send_ai_analysis_report(
                                    full_result,
                                    urgent_mode=is_urgent_filter
                                )
                                logger.info(f"✅ Полный AI анализ отправлен для {filter_name}")

                except Exception as e:
                    logger.error(f"❌ Ошибка AI анализа для {filter_name}: {e}")

        # Общая сводка
        if len(analysis_summaries) > 1:
            await self.telegram.send_analysis_summary(analysis_summaries)

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

            # AI анализ для urgent
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