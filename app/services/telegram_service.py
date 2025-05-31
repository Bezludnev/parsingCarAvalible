# app/services/telegram_service.py - ОБНОВЛЕННАЯ ВЕРСИЯ
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from app.config import settings
from app.models.car import Car
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self):
        self.bot = Bot(token=settings.telegram_bot_token)

    async def send_new_car_notification(self, car: Car):
        """Отправляет уведомление о новой машине"""
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
            raise
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка отправки уведомления для машины ID {car.id}: {e}")
            raise

    async def send_ai_analysis_report(self, analysis_result: Dict[str, Any]):
        """🤖 Отправляет AI анализ автомобилей в Telegram"""
        try:
            if not analysis_result.get("success", True):
                error_message = f"❌ <b>Ошибка AI анализа</b>\n\n{analysis_result.get('error', 'Неизвестная ошибка')}"
                await self.bot.send_message(
                    chat_id=settings.telegram_chat_id,
                    text=error_message,
                    parse_mode=ParseMode.HTML
                )
                return

            # Основное сообщение с анализом
            main_message = self._format_ai_analysis_message(analysis_result)

            # Отправляем основное сообщение
            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=main_message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

            # Если анализ очень длинный, отправляем детали отдельным сообщением
            detailed_analysis = analysis_result.get("detailed_analysis", "")
            if len(detailed_analysis) > 500:
                details_message = self._format_detailed_analysis_message(analysis_result)
                await self.bot.send_message(
                    chat_id=settings.telegram_chat_id,
                    text=details_message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )

            logger.info(f"✅ AI анализ отправлен в Telegram: {analysis_result.get('total_cars_analyzed', 0)} машин")

        except TelegramAPIError as e:
            logger.error(f"❌ Telegram API ошибка при отправке анализа: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка отправки AI анализа: {e}")
            raise

    def _format_ai_analysis_message(self, analysis_result: Dict[str, Any]) -> str:
        """Форматирует основное сообщение с AI анализом"""

        # Заголовок
        filter_name = analysis_result.get("filter_name", "машин")
        total_cars = analysis_result.get("total_cars_analyzed", 0)

        message = f"""🤖 <b>AI АНАЛИЗ АВТОМОБИЛЕЙ</b>

📊 <b>Проанализировано:</b> {total_cars} машин ({filter_name.title()})
🎯 <b>Модель:</b> o3-mini
⏱ <b>Время:</b> {self._format_timestamp(analysis_result.get("analysis_timestamp"))}

"""

        # Топ-3 рекомендации (обрезаем если слишком длинные)
        top_recommendations = analysis_result.get("top_recommendations", "")
        if top_recommendations:
            # Берем только первые 3 строки рекомендаций
            rec_lines = [line.strip() for line in top_recommendations.split('\n') if line.strip()]
            top_3 = rec_lines[:4]  # Заголовок + 3 рекомендации

            message += f"🏆 <b>ТОП-3 РЕКОМЕНДАЦИИ:</b>\n"
            for line in top_3[1:]:  # Пропускаем заголовок
                if line and not line.startswith('─'):
                    message += f"{line}\n"
            message += "\n"

        # Общие выводы (сокращенно)
        conclusions = analysis_result.get("general_conclusions", "")
        if conclusions:
            # Берем первые 2 абзаца выводов
            conclusion_lines = conclusions.split('\n\n')[:2]
            short_conclusions = '\n\n'.join(conclusion_lines)

            if len(short_conclusions) > 400:
                short_conclusions = short_conclusions[:400] + "..."

            message += f"📝 <b>КРАТКИЕ ВЫВОДЫ:</b>\n{short_conclusions}\n\n"

        # Рекомендованные ID машин
        recommended_ids = analysis_result.get("recommended_car_ids", [])
        if recommended_ids:
            message += f"⭐ <b>Рекомендованные ID:</b> {', '.join(map(str, recommended_ids))}\n\n"

        # Ссылка на детальный анализ
        message += f"<i>💡 Детальный анализ каждой машины отправлен отдельным сообщением</i>"

        return message

    def _format_detailed_analysis_message(self, analysis_result: Dict[str, Any]) -> str:
        """Форматирует детальное сообщение с анализом каждой машины"""

        detailed_analysis = analysis_result.get("detailed_analysis", "")

        if not detailed_analysis:
            return "📋 <b>Детальный анализ недоступен</b>"

        # Разбиваем на машины и берем только самое важное
        sections = detailed_analysis.split("Автомобиль #")

        message = "📋 <b>ДЕТАЛЬНЫЙ АНАЛИЗ ПО МАШИНАМ:</b>\n\n"

        for i, section in enumerate(sections[1:6], 1):  # Максимум 5 машин
            if section.strip():
                lines = section.split('\n')
                title_line = f"Автомобиль #{lines[0]}" if lines else f"Автомобиль #{i}"

                # Ищем рекомендацию
                recommendation = ""
                for line in lines:
                    if "📊 Рекомендация:" in line:
                        recommendation = line.replace("📊 Рекомендация:", "").strip()
                        break

                # Краткая справедливость цены
                price_assessment = ""
                for line in lines:
                    if "💰 Справедливость цены:" in line:
                        price_assessment = line.replace("💰 Справедливость цены:", "").strip()[:100]
                        break

                message += f"<b>{title_line}</b>\n"
                if price_assessment:
                    message += f"💰 {price_assessment}\n"
                if recommendation:
                    message += f"📊 <b>{recommendation}</b>\n"
                message += "\n"

        # Если слишком длинное, обрезаем
        if len(message) > 4000:
            message = message[:3900] + "...\n\n<i>Полный анализ доступен через API</i>"

        return message

    def _format_car_message(self, car: Car) -> str:
        """Форматирует сообщение о новой машине (существующий метод)"""
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

    def _format_timestamp(self, timestamp_str: str) -> str:
        """Форматирует timestamp для отображения"""
        if not timestamp_str:
            return "недавно"

        try:
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime("%d.%m.%Y %H:%M")
        except:
            return "недавно"

    async def send_quick_analysis_notification(self, analysis_result: Dict[str, Any]):
        """🚀 Отправляет краткое уведомление о быстром анализе"""
        try:
            if not analysis_result.get("success", True):
                return

            filter_name = analysis_result.get("filter_name", "машин")
            total_cars = analysis_result.get("total_cars", 0)
            quick_rec = analysis_result.get("quick_recommendation", "Нет рекомендации")

            message = f"""⚡ <b>Быстрый AI анализ</b>

🎯 <b>Фильтр:</b> {filter_name.title()}
📊 <b>Машин найдено:</b> {total_cars}

🤖 <b>Рекомендация:</b>
{quick_rec}

💡 <i>Для детального анализа используйте /analysis</i>
"""

            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )

            logger.info(f"✅ Быстрый анализ отправлен в Telegram: {filter_name}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки быстрого анализа: {e}")

    async def send_analysis_summary(self, summaries: List[Dict[str, Any]]):
        """📊 Отправляет сводку по всем фильтрам"""
        try:
            message = "📊 <b>СВОДКА AI АНАЛИЗА</b>\n\n"

            for summary in summaries:
                filter_name = summary.get("filter_name", "неизвестно")
                total_cars = summary.get("total_cars", 0)
                success = summary.get("success", False)

                status_emoji = "✅" if success else "❌"
                message += f"{status_emoji} <b>{filter_name.title()}:</b> {total_cars} машин\n"

                if success and summary.get("quick_recommendation"):
                    rec_short = summary["quick_recommendation"][:80] + "..."
                    message += f"   💡 {rec_short}\n"

                message += "\n"

            message += "<i>🤖 Анализ выполнен через o3-mini</i>"

            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )

            logger.info(f"✅ Сводка анализа отправлена: {len(summaries)} фильтров")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки сводки: {e}")

    async def close(self):
        """Закрытие сессии Telegram бота"""
        await self.bot.session.close()