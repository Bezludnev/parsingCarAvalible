# app/services/telegram_service.py - ОПТИМИЗИРОВАННАЯ ВЕРСИЯ с HTML отчетами
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile
from app.config import settings
from app.models.car import Car
from app.services.html_service import HTMLReportService
from typing import Dict, Any, List
import logging
import os

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self):
        self.bot = Bot(token=settings.telegram_bot_token)
        self.html_service = HTMLReportService()
        self.MAX_MESSAGE_LENGTH = 4000  # Безопасный лимит для Telegram

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
        """🤖 Отправляет AI анализ: краткую выжимку + HTML отчет"""
        try:
            if not analysis_result.get("success", True):
                error_message = f"❌ <b>Ошибка AI анализа</b>\n\n{analysis_result.get('error', 'Неизвестная ошибка')}"
                await self.bot.send_message(
                    chat_id=settings.telegram_chat_id,
                    text=error_message,
                    parse_mode=ParseMode.HTML
                )
                return

            # 1. Создаем HTML отчет
            html_file_path = self.html_service.generate_analysis_report(analysis_result)
            report_filename = os.path.basename(html_file_path)

            # 2. Отправляем краткую выжимку
            summary_message = self._create_analysis_summary(analysis_result, report_filename)

            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=summary_message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

            # 3. Отправляем HTML файл как документ
            try:
                html_file = FSInputFile(html_file_path, filename=report_filename)
                await self.bot.send_document(
                    chat_id=settings.telegram_chat_id,
                    document=html_file,
                    caption=f"📄 Полный AI отчет • {analysis_result.get('total_cars_analyzed', 0)} машин"
                )
                logger.info(f"✅ HTML отчет отправлен: {report_filename}")

            except Exception as e:
                logger.error(f"❌ Ошибка отправки HTML файла: {e}")
                # Отправляем хотя бы уведомление о создании файла
                await self.bot.send_message(
                    chat_id=settings.telegram_chat_id,
                    text=f"📄 HTML отчет создан: <code>{report_filename}</code>\n"
                         f"Файл сохранен локально, но не удалось отправить в Telegram.",
                    parse_mode=ParseMode.HTML
                )

            logger.info(f"✅ AI анализ отправлен: {analysis_result.get('total_cars_analyzed', 0)} машин")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки AI анализа: {e}")
            await self._send_error_notification(f"Ошибка создания отчета: {str(e)}")

    def _create_analysis_summary(self, analysis_result: Dict[str, Any], report_filename: str) -> str:
        """Создает краткую выжимку для Telegram (в пределах лимита)"""

        # Базовая информация
        filter_name = analysis_result.get("filter_name", "машин")
        total_cars = analysis_result.get("total_cars_analyzed", 0)
        model_used = analysis_result.get("model_used", "AI")
        recommended_ids = analysis_result.get("recommended_car_ids", [])

        # Начинаем с заголовка
        message = f"""🤖 <b>AI АНАЛИЗ ЗАВЕРШЕН</b>

📊 <b>Фильтр:</b> {filter_name.title()}
🚗 <b>Проанализировано:</b> {total_cars} машин
⭐ <b>Рекомендовано:</b> {len(recommended_ids)} машин
🧠 <b>Модель:</b> {model_used}

"""

        # Добавляем топ-3 рекомендации (сокращенно)
        top_recommendations = analysis_result.get("top_recommendations", "")
        if top_recommendations:
            short_recs = self._extract_short_recommendations(top_recommendations)
            message += f"🏆 <b>ТОП РЕКОМЕНДАЦИИ:</b>\n{short_recs}\n\n"

        # Краткие выводы (первые 2-3 предложения)
        conclusions = analysis_result.get("general_conclusions", "")
        if conclusions:
            short_conclusions = self._extract_short_conclusions(conclusions)
            message += f"📝 <b>ВЫВОДЫ:</b>\n{short_conclusions}\n\n"

        # Рекомендованные ID
        if recommended_ids:
            ids_str = ", ".join(str(id_) for id_ in recommended_ids[:8])  # Максимум 8 ID
            if len(recommended_ids) > 8:
                ids_str += f" (+{len(recommended_ids) - 8} еще)"
            message += f"⭐ <b>ID рекомендованных:</b> {ids_str}\n\n"

        # Уведомление о полном отчете
        message += f"📄 <b>Полный отчет:</b> <code>{report_filename}</code>\n"
        message += f"📎 <i>HTML файл отправлен отдельным сообщением</i>"

        # Проверяем лимит и обрезаем если нужно
        if len(message) > self.MAX_MESSAGE_LENGTH:
            message = message[
                      :self.MAX_MESSAGE_LENGTH - 100] + f"...\n\n📄 <b>Полный отчет:</b> <code>{report_filename}</code>"

        return message

    def _extract_short_recommendations(self, recommendations: str) -> str:
        """Извлекает короткие рекомендации (топ-3)"""

        lines = [line.strip() for line in recommendations.split('\n') if line.strip()]

        # Берем только первые 3 рекомендации
        rec_lines = []
        count = 0

        for line in lines:
            if line and not line.startswith('─') and count < 3:
                # Убираем лишние символы и сокращаем
                if any(char.isdigit() for char in line[:5]):  # Это пронумерованная рекомендация
                    short_line = line[:80] + "..." if len(line) > 80 else line
                    rec_lines.append(short_line)
                    count += 1

        return '\n'.join(rec_lines) if rec_lines else "См. полный отчет"

    def _extract_short_conclusions(self, conclusions: str) -> str:
        """Извлекает краткие выводы (первые 2-3 предложения)"""

        # Разбиваем на предложения
        sentences = [s.strip() for s in conclusions.replace('\n', ' ').split('.') if s.strip()]

        # Берем первые 2-3 предложения
        short_sentences = sentences[:3]
        short_text = '. '.join(short_sentences)

        if len(short_text) > 300:
            short_text = short_text[:300] + "..."

        return short_text + "." if short_text and not short_text.endswith('.') else short_text

    async def send_quick_analysis_notification(self, analysis_result: Dict[str, Any]):
        """⚡ Отправляет краткое уведомление о быстром анализе"""
        try:
            if not analysis_result.get("success", True):
                return

            filter_name = analysis_result.get("filter_name", "машин")
            total_cars = analysis_result.get("total_cars", 0)
            quick_rec = analysis_result.get("quick_recommendation", "Нет рекомендации")

            # Обрезаем рекомендацию если слишком длинная
            if len(quick_rec) > 200:
                quick_rec = quick_rec[:200] + "..."

            message = f"""⚡ <b>Быстрый AI анализ</b>

🎯 <b>Фильтр:</b> {filter_name.title()}
📊 <b>Машин:</b> {total_cars}

🤖 <b>Рекомендация:</b>
{quick_rec}

💡 <i>Для детального анализа используйте /analysis</i>
"""

            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )

            logger.info(f"✅ Быстрый анализ отправлен: {filter_name}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки быстрого анализа: {e}")

    async def send_analysis_summary(self, summaries: List[Dict[str, Any]]):
        """📊 Отправляет сводку по всем фильтрам"""
        try:
            message = "📊 <b>СВОДКА AI АНАЛИЗА</b>\n\n"

            total_reports = 0
            for summary in summaries:
                filter_name = summary.get("filter_name", "неизвестно")
                total_cars = summary.get("total_cars", 0)
                success = summary.get("success", False)

                status_emoji = "✅" if success else "❌"
                message += f"{status_emoji} <b>{filter_name.title()}:</b> {total_cars} машин\n"

                if success:
                    total_reports += 1
                    quick_rec = summary.get("quick_recommendation", "")
                    if quick_rec:
                        rec_short = quick_rec[:60] + "..." if len(quick_rec) > 60 else quick_rec
                        message += f"   💡 {rec_short}\n"

                message += "\n"

            message += f"📄 <b>Создано HTML отчетов:</b> {total_reports}\n"
            message += "<i>🤖 Файлы отправлены отдельными сообщениями</i>"

            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )

            logger.info(f"✅ Сводка анализа отправлена: {len(summaries)} фильтров, {total_reports} отчетов")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки сводки: {e}")

    async def send_reports_list(self):
        """📋 Отправляет список созданных HTML отчетов"""
        try:
            reports = self.html_service.get_reports_list(10)

            if not reports:
                message = "📋 <b>Список отчетов</b>\n\nНет созданных отчетов"
            else:
                message = "📋 <b>Последние HTML отчеты</b>\n\n"

                for i, report in enumerate(reports, 1):
                    filename = report["filename"]
                    size = report["size_mb"]
                    created = report["created"]

                    message += f"{i}. <code>{filename}</code>\n"
                    message += f"   📅 {created} • {size} MB\n\n"

                if len(reports) == 10:
                    message += "<i>Показаны последние 10 отчетов</i>"

            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            logger.error(f"❌ Ошибка отправки списка отчетов: {e}")

    async def _send_error_notification(self, error_text: str):
        """Отправляет уведомление об ошибке"""
        try:
            message = f"❌ <b>Ошибка системы</b>\n\n{error_text}"
            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление об ошибке: {e}")

    def _format_car_message(self, car: Car) -> str:
        """Форматирует сообщение о новой машине"""
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
        """Закрытие сессии Telegram бота"""
        await self.bot.session.close()