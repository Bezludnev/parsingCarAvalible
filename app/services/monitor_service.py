# app/services/monitor_service.py - ОБНОВЛЕННАЯ ВЕРСИЯ
from app.services.scraper_service import ScraperService
from app.services.telegram_service import TelegramService
from app.services.analysis_service import AnalysisService  # ДОБАВЛЕНО
from app.repository.car_repository import CarRepository
from app.database import async_session
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class MonitorService:
    def __init__(self):
        self.scraper = ScraperService()
        self.telegram = TelegramService()
        self.analysis = AnalysisService()  # ДОБАВЛЕНО

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
            cars = await self.scraper.scrape_cars(filter_name)
            logger.info(f"Найдено {len(cars)} объявлений для фильтра {filter_name}")

            new_cars_count = 0
            for car_data in cars:
                existing_car = await repo.get_by_link(car_data.link)
                if not existing_car:
                    new_car = await repo.create(car_data)
                    logger.info(f"Новая машина добавлена: {new_car.title}")
                    urgent = await self._is_urgent(new_car.description or "")
                    await self.telegram.send_new_car_notification(new_car, urgent=urgent)
                    await repo.mark_as_notified(new_car.id)
                    new_cars_count += 1

            return new_cars_count

        except Exception as e:
            logger.error(f"Ошибка при обработке фильтра {filter_name}: {e}")
            return 0

    async def check_new_cars(self):
        """Основная функция для проверки новых машин + AI анализ"""
        logger.info("Начинаем проверку новых объявлений...")

        new_cars_found = {}  # {filter_name: количество_новых_машин}

        async with async_session() as session:
            repo = CarRepository(session)

            for filter_name in settings.car_filters:
                count = await self._process_filter(filter_name, repo)
                new_cars_found[filter_name] = count

        # НОВАЯ ЛОГИКА: AI анализ если найдены новые машины
        total_new_cars = sum(new_cars_found.values())

        if total_new_cars > 0:
            logger.info(f"🤖 Найдено {total_new_cars} новых машин, запускаем AI анализ...")
            await self._run_ai_analysis_for_new_cars(new_cars_found)
        else:
            logger.info("Новых машин не найдено, AI анализ не требуется")

        logger.info("Проверка завершена")

    async def _run_ai_analysis_for_new_cars(self, new_cars_found: dict):
        """Запускает AI анализ для фильтров с новыми машинами"""

        analysis_summaries = []

        for filter_name, new_count in new_cars_found.items():
            if new_count > 0:  # Только для фильтров с новыми машинами
                try:
                    logger.info(f"🔍 AI анализ для {filter_name} ({new_count} новых машин)")

                    # Быстрый анализ для уведомления
                    quick_result = await self.analysis.get_quick_insight(filter_name)

                    if quick_result.get("success"):
                        await self.telegram.send_quick_analysis_notification(quick_result)
                        analysis_summaries.append(quick_result)

                        # Если найдено достаточно машин (>=3), делаем полный анализ
                        if quick_result.get("total_cars", 0) >= 3:
                            full_result = await self.analysis.analyze_cars_by_filter(filter_name, 10)

                            if full_result.get("success"):
                                await self.telegram.send_ai_analysis_report(full_result)
                                logger.info(f"✅ Полный AI анализ отправлен для {filter_name}")

                except Exception as e:
                    logger.error(f"❌ Ошибка AI анализа для {filter_name}: {e}")
                    analysis_summaries.append({
                        "filter_name": filter_name,
                        "success": False,
                        "error": str(e)
                    })

        # Отправляем общую сводку если анализировали несколько фильтров
        if len(analysis_summaries) > 1:
            await self.telegram.send_analysis_summary(analysis_summaries)

    async def run_manual_ai_analysis(self, filter_name: str = None):
        """🔧 Ручной запуск AI анализа (для API endpoint)"""

        if filter_name:
            # Анализ конкретного фильтра
            logger.info(f"🔧 Ручной AI анализ для {filter_name}")

            try:
                result = await self.analysis.analyze_cars_by_filter(filter_name, 15)

                if result.get("success"):
                    await self.telegram.send_ai_analysis_report(result)
                    return {"status": "success", "filter": filter_name,
                            "cars_analyzed": result.get("total_cars_analyzed", 0)}
                else:
                    return {"status": "error", "filter": filter_name, "error": result.get("error")}

            except Exception as e:
                logger.error(f"❌ Ошибка ручного анализа {filter_name}: {e}")
                return {"status": "error", "filter": filter_name, "error": str(e)}

        else:
            # Анализ всех фильтров
            logger.info("🔧 Ручной AI анализ всех фильтров")

            results = []

            for filter_name in settings.car_filters:
                try:
                    quick_result = await self.analysis.get_quick_insight(filter_name)

                    if quick_result.get("success") and quick_result.get("total_cars", 0) >= 2:
                        full_result = await self.analysis.analyze_cars_by_filter(filter_name, 10)

                        if full_result.get("success"):
                            await self.telegram.send_ai_analysis_report(full_result)
                            results.append({"filter": filter_name, "status": "success",
                                            "cars": full_result.get("total_cars_analyzed", 0)})
                        else:
                            results.append(
                                {"filter": filter_name, "status": "error", "error": full_result.get("error")})
                    else:
                        results.append({"filter": filter_name, "status": "skipped", "reason": "insufficient_cars"})

                except Exception as e:
                    logger.error(f"❌ Ошибка анализа {filter_name}: {e}")
                    results.append({"filter": filter_name, "status": "error", "error": str(e)})

            return {"status": "completed", "results": results}

