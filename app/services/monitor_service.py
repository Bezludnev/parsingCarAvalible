# app/services/monitor_service.py
from app.services.scraper_service import ScraperService
from app.services.telegram_service import TelegramService
from app.repository.car_repository import CarRepository
from app.database import async_session
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class MonitorService:
    def __init__(self):
        self.scraper = ScraperService()
        self.telegram = TelegramService()

    async def check_new_cars(self):
        """Основная функция для проверки новых машин"""
        logger.info("Начинаем проверку новых объявлений...")

        async with async_session() as session:
            repo = CarRepository(session)

            for filter_name in settings.car_filters.keys():
                try:
                    # Scrape cars
                    cars = await self.scraper.scrape_cars(filter_name)
                    logger.info(f"Найдено {len(cars)} объявлений для фильтра {filter_name}")

                    # Check for new cars
                    for car_data in cars:
                        existing_car = await repo.get_by_link(car_data.link)

                        if not existing_car:
                            # New car found!
                            new_car = await repo.create(car_data)
                            logger.info(f"Новая машина добавлена: {new_car.title}")

                            # Send notification
                            await self.telegram.send_new_car_notification(new_car)
                            await repo.mark_as_notified(new_car.id)

                except Exception as e:
                    logger.error(f"Ошибка при обработке фильтра {filter_name}: {e}")

        logger.info("Проверка завершена")