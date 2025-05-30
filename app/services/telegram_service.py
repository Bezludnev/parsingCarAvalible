# app/services/telegram_service.py
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from app.config import settings
from app.models.car import Car
import logging

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self):
        self.bot = Bot(token=settings.telegram_bot_token)

    async def send_new_car_notification(self, car: Car):
        message = self._format_car_message(car)
        try:
            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )
            logger.info(f"✅ Уведомление отправлено для машины ID: {car.id}")
        except TelegramAPIError as e:
            logger.error(f"❌ Telegram API ошибка для машины ID {car.id}: {e}")
            raise  # Перебрасываем исключение для обработки в monitor_service
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка отправки уведомления для машины ID {car.id}: {e}")
            raise

    def _format_car_message(self, car: Car) -> str:
        return f"""
🚗 <b>Новое объявление - {car.brand}</b>

📝 <b>Заголовок:</b> {car.title}
💰 <b>Цена:</b> {car.price}
📅 <b>Год:</b> {car.year or 'нет данных'}
🛣 <b>Пробег:</b> {f"{car.mileage:,} км" if car.mileage else 'нет данных'}
📍 <b>Место:</b> {car.place}
📆 <b>Дата публикации:</b> {car.date_posted}

🔗 <a href="{car.link}">Посмотреть объявление</a>

⚙️ <b>Характеристики:</b> {car.features}
        """.strip()

    async def close(self):
        await self.bot.session.close()