# app/services/monitor_service.py - ИСПРАВЛЕН: убран AI urgent detection
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
        """🔧 ИСПРАВЛЕНО: Только keyword detection, БЕЗ AI вызовов"""
        logger.debug("🔍 _is_urgent() called - using keywords only")

        if not text:
            logger.debug("❌ _is_urgent() - no text provided")
            return False

        # Только ключевые слова, БЕЗ AI
        keywords = [
            "срочно", "urgent", "быстро", "price drop", "недорого", "must sell",
            "asap", "reduced", "negotiable", "торг", "обмен", "выгодно", "дешево"
        ]
        text_lower = text.lower()
        found_keyword = None

        for keyword in keywords:
            if keyword in text_lower:
                found_keyword = keyword
                break

        if found_keyword:
            logger.info(f"🔥 _is_urgent() - URGENT detected by keyword: '{found_keyword}'")
            return True
        else:
            logger.debug("✅ _is_urgent() - no urgent keywords found")
            return False

    async def _process_filter(self, filter_name: str, repo: CarRepository) -> int:
        """Скрапинг и обработка одного фильтра с оптимизацией"""
        logger.info(f"🎯 _process_filter() called for: {filter_name}")

        try:
            filter_config = settings.car_filters.get(filter_name, {})
            is_urgent_filter = filter_config.get("urgent_mode", False)

            logger.info(f"📋 _process_filter({filter_name}) - urgent_mode: {is_urgent_filter}")

            # Получаем существующие ссылки для этого фильтра
            existing_links = await repo.get_existing_links_by_filter(filter_name)
            logger.info(f"📋 _process_filter({filter_name}): {len(existing_links)} existing links in DB")

            # Передаем existing_links в scraper для оптимизации
            cars = await self.scraper.scrape_cars(filter_name, existing_links)
            logger.info(f"{'🔥' if is_urgent_filter else '📊'} "
                        f"_process_filter({filter_name}): {len(cars)} NEW cars found")

            new_cars_count = 0
            for car_data in cars:
                logger.debug(f"🔄 _process_filter({filter_name}) - processing car: {car_data.title[:50]}")

                # Дополнительная проверка на всякий случай
                existing_car = await repo.get_by_link(car_data.link)
                if not existing_car:
                    new_car = await repo.create(car_data)
                    logger.info(f"✅ _process_filter({filter_name}) - NEW CAR: {new_car.title}")

                    # 🔧 ИСПРАВЛЕНО: Проверяем urgent статус БЕЗ AI
                    logger.debug(f"🔍 _process_filter({filter_name}) - checking urgent status for car ID: {new_car.id}")
                    urgent = await self._is_urgent(new_car.description or "")

                    # Отправляем уведомление
                    logger.info(f"📱 _process_filter({filter_name}) - sending notification for car ID: {new_car.id}")
                    await self.telegram.send_new_car_notification(
                        new_car,
                        urgent=urgent or is_urgent_filter,
                        urgent_filter=is_urgent_filter
                    )

                    await repo.mark_as_notified(new_car.id)
                    new_cars_count += 1
                    logger.debug(f"✅ _process_filter({filter_name}) - car ID {new_car.id} processed successfully")

            logger.info(f"🎯 _process_filter({filter_name}) COMPLETED: {new_cars_count} new cars processed")
            return new_cars_count

        except Exception as e:
            logger.error(f"❌ _process_filter({filter_name}) ERROR: {e}")
            return 0

    async def check_new_cars(self):
        """Основная функция для проверки новых машин БЕЗ автоматического AI анализа"""
        logger.info("🔍 check_new_cars() called - starting car monitoring check...")

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

            logger.info(
                f"📊 check_new_cars() - filters split: {len(urgent_filters)} urgent, {len(regular_filters)} regular")

            # Сначала обрабатываем URGENT фильтры (приоритет)
            if urgent_filters:
                logger.info(f"🔥 check_new_cars() - processing URGENT filters: {urgent_filters}")

                for filter_name in urgent_filters:
                    logger.info(f"🔥 check_new_cars() - starting urgent filter: {filter_name}")
                    count = await self._process_filter(filter_name, repo)
                    new_cars_found[filter_name] = count
                    urgent_filters_stats[filter_name] = count
                    logger.info(f"🔥 check_new_cars() - urgent filter {filter_name} completed: {count} cars")

                # Если в urgent найдены машины - отправляем сводку
                urgent_total = sum(urgent_filters_stats.values())
                if urgent_total > 0:
                    logger.info(f"🔥 check_new_cars() - sending urgent summary: {urgent_total} total urgent cars")
                    await self.telegram.send_urgent_summary(urgent_filters_stats)

            # Затем обрабатываем обычные фильтры
            logger.info(f"📊 check_new_cars() - processing REGULAR filters: {regular_filters}")

            for filter_name in regular_filters:
                logger.info(f"📊 check_new_cars() - starting regular filter: {filter_name}")
                count = await self._process_filter(filter_name, repo)
                new_cars_found[filter_name] = count
                logger.info(f"📊 check_new_cars() - regular filter {filter_name} completed: {count} cars")

        # Простая сводка без AI анализа
        total_new_cars = sum(new_cars_found.values())

        if total_new_cars > 0:
            logger.info(f"✅ check_new_cars() COMPLETED: {total_new_cars} new cars found total")

            # Краткая статистика в лог
            for filter_name, count in new_cars_found.items():
                if count > 0:
                    urgent_mark = "🔥" if filter_name in urgent_filters_stats else "📊"
                    logger.info(f"  {urgent_mark} check_new_cars() - {filter_name}: {count} cars")
        else:
            logger.info("😴 check_new_cars() COMPLETED: no new cars found")

        logger.info("✅ check_new_cars() FINISHED (AI analysis disabled)")

    async def run_urgent_check_only(self):
        """🔥 Отдельная проверка только urgent фильтров"""
        logger.info("🔥 run_urgent_check_only() called - checking only URGENT filters...")

        urgent_found = {}

        async with async_session() as session:
            repo = CarRepository(session)

            urgent_filters = [name for name, config in settings.car_filters.items()
                              if config.get("urgent_mode", False)]

            logger.info(f"🔥 run_urgent_check_only() - urgent filters: {urgent_filters}")

            for filter_name in urgent_filters:
                logger.info(f"🔥 run_urgent_check_only() - processing: {filter_name}")
                count = await self._process_filter(filter_name, repo)
                urgent_found[filter_name] = count

        total_urgent = sum(urgent_found.values())

        if total_urgent > 0:
            logger.info(f"🔥 run_urgent_check_only() - found {total_urgent} urgent cars")
            await self.telegram.send_urgent_summary(urgent_found)

            # AI анализ для urgent (опционально)
            for filter_name, count in urgent_found.items():
                if count > 0:
                    try:
                        logger.info(f"🤖 run_urgent_check_only() - starting AI analysis for {filter_name}")
                        quick_result = await self.analysis.get_quick_insight(filter_name)
                        if quick_result.get("success"):
                            await self.telegram.send_quick_analysis_notification(
                                quick_result, urgent_mode=True
                            )
                            logger.info(f"✅ run_urgent_check_only() - AI analysis sent for {filter_name}")
                    except Exception as e:
                        logger.error(f"❌ run_urgent_check_only() - AI analysis error for {filter_name}: {e}")
        else:
            logger.info("😴 run_urgent_check_only() - no urgent cars found")

    async def run_manual_ai_analysis(self, filter_name: str = None):
        """🔧 Ручной запуск AI анализа с поддержкой urgent режима"""
        logger.info(f"🔧 run_manual_ai_analysis() called with filter: {filter_name}")

        if filter_name:
            # Анализ конкретного фильтра
            logger.info(f"🔧 run_manual_ai_analysis() - single filter analysis: {filter_name}")

            filter_config = settings.car_filters.get(filter_name, {})
            is_urgent = filter_config.get("urgent_mode", False)

            try:
                logger.info(f"🤖 run_manual_ai_analysis() - calling analyze_cars_by_filter({filter_name})")
                result = await self.analysis.analyze_cars_by_filter(filter_name, 15)

                if result.get("success"):
                    logger.info(f"📱 run_manual_ai_analysis() - sending AI report for {filter_name}")
                    await self.telegram.send_ai_analysis_report(result, urgent_mode=is_urgent)
                    return {
                        "status": "success",
                        "filter": filter_name,
                        "urgent_mode": is_urgent,
                        "cars_analyzed": result.get("total_cars_analyzed", 0)
                    }
                else:
                    logger.error(
                        f"❌ run_manual_ai_analysis() - analysis failed for {filter_name}: {result.get('error')}")
                    return {"status": "error", "filter": filter_name, "error": result.get("error")}

            except Exception as e:
                logger.error(f"❌ run_manual_ai_analysis() - exception for {filter_name}: {e}")
                return {"status": "error", "filter": filter_name, "error": str(e)}

        else:
            # Анализ всех фильтров
            logger.info("🔧 run_manual_ai_analysis() - analyzing ALL filters")
            results = []

            for filter_name, config in settings.car_filters.items():
                is_urgent = config.get("urgent_mode", False)

                try:
                    logger.info(f"🤖 run_manual_ai_analysis() - quick insight for {filter_name}")
                    quick_result = await self.analysis.get_quick_insight(filter_name)

                    if quick_result.get("success") and quick_result.get("total_cars", 0) >= 2:
                        logger.info(f"🤖 run_manual_ai_analysis() - full analysis for {filter_name}")
                        full_result = await self.analysis.analyze_cars_by_filter(filter_name, 10)

                        if full_result.get("success"):
                            logger.info(f"📱 run_manual_ai_analysis() - sending report for {filter_name}")
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
                        logger.info(f"⏭️ run_manual_ai_analysis() - skipping {filter_name} (insufficient cars)")
                        results.append({
                            "filter": filter_name,
                            "status": "skipped",
                            "urgent_mode": is_urgent,
                            "reason": "insufficient_cars"
                        })

                except Exception as e:
                    logger.error(f"❌ run_manual_ai_analysis() - error for {filter_name}: {e}")
                    results.append({
                        "filter": filter_name,
                        "status": "error",
                        "urgent_mode": is_urgent,
                        "error": str(e)
                    })

            logger.info(f"🔧 run_manual_ai_analysis() - ALL filters completed: {len(results)} results")
            return {"status": "completed", "results": results}

    async def get_filters_status(self) -> Dict:
        """📊 Статус всех фильтров с разделением на обычные/urgent"""
        logger.info("📊 get_filters_status() called")

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

        result = {
            "total_filters": len(settings.car_filters),
            "regular_filters": regular_filters,
            "urgent_filters": urgent_filters,
            "urgent_count": len(urgent_filters),
            "regular_count": len(regular_filters)
        }

        logger.info(f"📊 get_filters_status() - returning {result['total_filters']} filters")
        return result