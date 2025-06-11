# app/services/changes_service.py - отслеживание изменений в объявлениях
from app.services.scraper_service import ScraperService
from app.services.telegram_service import TelegramService
from app.repository.car_repository import CarRepository
from app.database import async_session
from app.models.car import Car
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ChangesTrackingService:
    def __init__(self):
        self.scraper = ScraperService()
        self.telegram = TelegramService()

    async def check_all_cars_for_changes(self):
        """🔄 Главный метод: проверка всех машин на изменения"""
        logger.info("🔄 check_all_cars_for_changes() - starting daily changes check...")

        async with async_session() as session:
            repo = CarRepository(session)

            # Получаем машины которые не проверялись больше 20 часов
            cutoff_time = datetime.now() - timedelta(hours=20)
            cars_to_check = await repo.get_cars_for_changes_check(cutoff_time)

            logger.info(f"📋 Found {len(cars_to_check)} cars to check for changes")

            if not cars_to_check:
                logger.info("😴 No cars need changes check")
                return

            total_changes = 0
            price_changes = 0
            description_changes = 0
            unavailable_count = 0

            # Проверяем изменения по батчам
            batch_size = 20
            for i in range(0, len(cars_to_check), batch_size):
                batch = cars_to_check[i:i + batch_size]
                logger.info(f"🔄 Processing batch {i // batch_size + 1}: {len(batch)} cars")

                for car in batch:
                    try:
                        changes = await self._check_single_car_changes(car, repo)
                        if changes:
                            total_changes += 1
                            if changes.get("price_changed"):
                                price_changes += 1
                            if changes.get("description_changed"):
                                description_changes += 1

                            # Отправляем уведомление об изменениях
                            await self.telegram.send_car_changes_notification(car, changes)

                        # Обновляем время последней проверки
                        await repo.update_last_checked(car.id)

                    except Exception as e:
                        if "404" in str(e) or "не найдено" in str(e).lower():
                            unavailable_count += 1
                            logger.warning(f"❌ Car {car.id} unavailable (probably sold): {car.title[:50]}")
                            await repo.mark_as_unavailable(car.id)
                        else:
                            logger.error(f"❌ Error checking car {car.id}: {e}")

                # Пауза между батчами
                import asyncio
                await asyncio.sleep(2)

            # Отправляем общую сводку
            if total_changes > 0 or unavailable_count > 0:
                await self.telegram.send_daily_changes_summary({
                    "total_checked": len(cars_to_check),
                    "total_changes": total_changes,
                    "price_changes": price_changes,
                    "description_changes": description_changes,
                    "unavailable_count": unavailable_count
                })

            logger.info(f"✅ Daily changes check completed: {total_changes} changes, "
                        f"{unavailable_count} unavailable cars")

    async def _check_single_car_changes(self, car: Car, repo: CarRepository) -> Optional[Dict[str, Any]]:
        """🔍 Проверка изменений в одном объявлении"""
        logger.debug(f"🔍 Checking changes for car {car.id}: {car.title[:30]}")

        try:
            # Получаем актуальные данные с сайта
            current_data = await self.scraper.get_single_car_data(car.link)

            if not current_data:
                raise Exception("Car data not found - probably removed/sold")

            changes = {}
            has_changes = False

            # Проверяем изменение цены
            current_price = current_data.get("price", "").strip()
            if current_price and current_price != car.price:
                changes["price_changed"] = True
                changes["old_price"] = car.price
                changes["new_price"] = current_price

                # Обновляем в базе
                await repo.update_price_change(car.id, car.price, current_price)
                has_changes = True

                logger.info(f"💰 Price changed for car {car.id}: {car.price} → {current_price}")

            # Проверяем изменение описания
            current_description = current_data.get("description", "").strip()
            if current_description and current_description != (car.description or ""):
                changes["description_changed"] = True
                changes["old_description"] = car.description or ""
                changes["new_description"] = current_description

                # Обновляем в базе
                await repo.update_description_change(car.id, car.description, current_description)
                has_changes = True

                logger.info(f"📝 Description changed for car {car.id}")

            return changes if has_changes else None

        except Exception as e:
            logger.error(f"❌ Error checking car {car.id}: {e}")
            raise

    async def check_specific_cars_changes(self, car_ids: List[int]) -> Dict[str, Any]:
        """🎯 Проверка конкретных машин (для API endpoint)"""
        logger.info(f"🎯 check_specific_cars_changes() called for {len(car_ids)} cars")

        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_cars_by_ids(car_ids)

            results = []
            for car in cars:
                try:
                    changes = await self._check_single_car_changes(car, repo)
                    await repo.update_last_checked(car.id)

                    results.append({
                        "car_id": car.id,
                        "title": car.title,
                        "has_changes": changes is not None,
                        "changes": changes or {}
                    })

                    if changes:
                        await self.telegram.send_car_changes_notification(car, changes)

                except Exception as e:
                    results.append({
                        "car_id": car.id,
                        "title": car.title,
                        "error": str(e)
                    })

            return {
                "status": "completed",
                "checked_cars": len(car_ids),
                "results": results
            }

    async def get_recent_changes_summary(self, days: int = 7) -> Dict[str, Any]:
        """📊 Сводка изменений за последние дни"""
        async with async_session() as session:
            repo = CarRepository(session)
            summary = await repo.get_changes_summary(days)
            return summary