# app/services/telegram_service.py - С SCHEDULED АНАЛИЗОМ
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile
from app.config import settings
from app.models.car import Car
from app.services.html_service import HTMLReportService
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self):
        self.bot = Bot(token=settings.telegram_bot_token)
        self.html_service = HTMLReportService()
        self.MAX_MESSAGE_LENGTH = 4000  # Безопасный лимит для Telegram

    async def send_new_car_notification(self, car: Car, urgent: bool = False, urgent_filter: bool = False):
        """Отправляет уведомление о новой машине"""
        message = self._format_car_message(car, urgent, urgent_filter)
        try:
            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )
            urgent_status = "🔥 URGENT" if urgent or urgent_filter else "обычное"
            logger.info(f"✅ {urgent_status} уведомление отправлено для машины ID: {car.id}")
        except TelegramAPIError as e:
            logger.error(f"❌ Telegram API ошибка для машины ID {car.id}: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка отправки уведомления для машины ID {car.id}: {e}")
            raise

    async def send_scheduled_analysis_report(self, analysis_result: Dict[str, Any]):
        """🤖 Отправляет scheduled AI анализ базы данных"""
        try:
            if not analysis_result.get("success", True):
                await self._send_error_notification(f"Scheduled анализ не удался: {analysis_result.get('error')}")
                return

            # Создаем HTML отчет
            html_file_path = self.html_service.generate_analysis_report(analysis_result)
            report_filename = os.path.basename(html_file_path)

            # Специальное сообщение для scheduled анализа
            current_time = datetime.now().strftime("%H:%M")
            total_cars = analysis_result.get("total_cars_analyzed", 0)
            recommended_count = len(analysis_result.get("recommended_car_ids", []))
            brands_count = len(analysis_result.get("brands_analyzed", []))

            message = f"""🤖 <b>SCHEDULED AI АНАЛИЗ</b> • {current_time}

📊 <b>Полный анализ базы данных:</b>
🚗 Проанализировано: {total_cars} автомобилей
🏷️ Брендов: {brands_count}
⭐ Лучших предложений: {recommended_count}

💡 <b>Краткие выводы:</b>
{self._extract_short_conclusions(analysis_result.get("general_conclusions", ""))[:300]}

📄 <b>Полный отчет:</b> <code>{report_filename}</code>
📎 <i>HTML файл с детальным анализом</i>

🔍 <i>Следующий анализ: в {'09:00' if datetime.now().hour >= 18 else '18:00'}</i>
"""

            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

            # Отправляем HTML файл
            try:
                html_file = FSInputFile(html_file_path, filename=report_filename)
                await self.bot.send_document(
                    chat_id=settings.telegram_chat_id,
                    document=html_file,
                    caption=f"📊 Scheduled анализ • {total_cars} машин • {recommended_count} рекомендаций"
                )
                logger.info(f"✅ Scheduled анализ отправлен: {report_filename}")

            except Exception as e:
                logger.error(f"❌ Ошибка отправки scheduled HTML: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки scheduled анализа: {e}")
            await self._send_error_notification(f"Ошибка scheduled анализа: {str(e)}")

    async def send_top_deals_notification(self, analysis_result: Dict[str, Any], recommended_ids: List[int]):
        """💎 Отправляет уведомление о топовых предложениях"""
        try:
            if not recommended_ids:
                return

            cars_data = analysis_result.get("cars_data", [])
            recommended_cars = [car for car in cars_data if car.get("id") in recommended_ids]

            if not recommended_cars:
                return

            message = f"""💎 <b>ТОП ПРЕДЛОЖЕНИЯ ДНЯ</b>

🎯 <b>Найдено {len(recommended_cars)} лучших вариантов:</b>

"""

            for i, car in enumerate(recommended_cars[:5], 1):  # Топ-5
                car_id = car.get("id")
                title = car.get("title", "")[:50] + ("..." if len(car.get("title", "")) > 50 else "")
                brand = car.get("brand", "")
                year = car.get("year", "")
                price = car.get("price", "")
                mileage = car.get("mileage")
                link = car.get("link", "")

                # Ищем описание с признаками хорошего предложения
                description = car.get("description", "")
                deal_indicators = self._extract_deal_indicators(description)

                mileage_text = f"{mileage:,} км" if mileage else "н/д"

                message += f"""<b>{i}. {brand} {year}</b>
📝 {title}
💰 {price} • 🛣 {mileage_text}
{deal_indicators}
🔗 <a href="{link}">Посмотреть</a>

"""

            message += f"""
🤖 <i>Анализ основан на соотношении цена/качество, состоянии и описании</i>
⏰ <i>Обновляется 2 раза в день</i>
"""

            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )

            logger.info(f"✅ Топ предложения отправлены: {len(recommended_cars)} машин")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки топ предложений: {e}")

    def _extract_deal_indicators(self, description: str) -> str:
        """Извлекает индикаторы хорошего предложения из описания"""
        if not description:
            return "📋 <i>без описания</i>"

        indicators = []
        desc_lower = description.lower()

        # Позитивные индикаторы
        if any(word in desc_lower for word in ["срочно", "urgent", "переезд", "быстро"]):
            indicators.append("🔥 срочно")
        if any(word in desc_lower for word in ["отличное", "идеальное", "perfect", "excellent"]):
            indicators.append("✨ отличное состояние")
        if any(word in desc_lower for word in ["сервис", "то", "обслуживание", "service"]):
            indicators.append("🔧 сервисная история")
        if any(word in desc_lower for word in ["один владелец", "one owner", "первый"]):
            indicators.append("👤 один владелец")
        if any(word in desc_lower for word in ["снижена", "скидка", "reduced", "discount"]):
            indicators.append("💸 снижена цена")

        if indicators:
            return "💡 " + " • ".join(indicators[:3])  # Максимум 3 индикатора
        else:
            # Показываем начало описания
            desc_short = description[:80] + "..." if len(description) > 80 else description
            return f"📝 <i>{desc_short}</i>"

    async def send_ai_analysis_report(self, analysis_result: Dict[str, Any], urgent_mode: bool = False):
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
            summary_message = self._create_analysis_summary(analysis_result, report_filename, urgent_mode)

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

    def _create_analysis_summary(self, analysis_result: Dict[str, Any], report_filename: str,
                                 urgent_mode: bool = False) -> str:
        """Создает краткую выжимку для Telegram (в пределах лимита)"""

        # Базовая информация
        filter_name = analysis_result.get("filter_name", "машин")
        total_cars = analysis_result.get("total_cars_analyzed", 0)
        model_used = analysis_result.get("model_used", "AI")
        recommended_ids = analysis_result.get("recommended_car_ids", [])

        # Начинаем с заголовка
        urgent_emoji = "🔥🔥 " if urgent_mode else ""
        urgent_text = "URGENT " if urgent_mode else ""

        message = f"""{urgent_emoji}🤖 <b>{urgent_text}AI АНАЛИЗ ЗАВЕРШЕН</b>

📊 <b>Фильтр:</b> {filter_name.title()} {'(🔥 URGENT режим)' if urgent_mode else ''}
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

    async def send_quick_analysis_notification(self, analysis_result: Dict[str, Any], urgent_mode: bool = False):
        """⚡ Отправляет краткое уведомление о быстром анализе"""
        try:
            if not analysis_result.get("success", True):
                return

            filter_name = analysis_result.get("filter_name", "машин")
            total_cars = analysis_result.get("total_cars", 0)
            quick_rec = analysis_result.get("quick_recommendation", "Нет рекомендации")
            rec_link = analysis_result.get("recommended_link")

            # Обрезаем рекомендацию если слишком длинная
            if len(quick_rec) > 200:
                quick_rec = quick_rec[:200] + "..."

            urgent_emoji = "🔥⚡ " if urgent_mode else "⚡ "
            urgent_text = "URGENT " if urgent_mode else ""

            message = f"""{urgent_emoji}<b>{urgent_text}Быстрый AI анализ</b>

🎯 <b>Фильтр:</b> {filter_name.title()} {'(🔥 URGENT)' if urgent_mode else ''}
📊 <b>Машин:</b> {total_cars}

🤖 <b>Рекомендация:</b>
{quick_rec}
"""

            if rec_link:
                message += f"\n🔗 <a href=\"{rec_link}\">Посмотреть объявление</a>"

            message += """

💡 <i>Для детального анализа используйте /analysis</i>
"""

            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )

            logger.info(f"✅ Быстрый анализ отправлен: {filter_name} {'(URGENT)' if urgent_mode else ''}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки быстрого анализа: {e}")

    async def send_urgent_summary(self, urgent_stats: Dict[str, int]):
        """🔥 Отправляет сводку по urgent фильтрам"""
        try:
            total_urgent = sum(urgent_stats.values())

            if total_urgent == 0:
                return

            message = f"""🔥🔥 <b>URGENT СВОДКА</b> 🔥🔥

🚨 <b>Найдено {total_urgent} срочных объявлений!</b>

"""

            for filter_name, count in urgent_stats.items():
                if count > 0:
                    message += f"🔥 <b>{filter_name}:</b> {count} машин\n"

            message += f"""

⚡ <i>AI анализ запущен автоматически</i>
🔗 <i>Детальные отчеты следуют...</i>
"""

            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )

            logger.info(f"🔥 Urgent сводка отправлена: {total_urgent} машин из {len(urgent_stats)} фильтров")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки urgent сводки: {e}")

    async def send_analysis_summary(self, summaries: List[Dict[str, Any]]):
        """📊 Отправляет сводку по всем фильтрам"""
        try:
            message = "📊 <b>СВОДКА AI АНАЛИЗА</b>\n\n"

            total_reports = 0
            urgent_count = 0

            for summary in summaries:
                filter_name = summary.get("filter_name", "неизвестно")
                total_cars = summary.get("total_cars", 0)
                success = summary.get("success", False)

                # Проверяем если это urgent фильтр
                filter_config = settings.car_filters.get(filter_name, {})
                is_urgent = filter_config.get("urgent_mode", False)

                status_emoji = "✅" if success else "❌"
                urgent_emoji = " 🔥" if is_urgent else ""

                message += f"{status_emoji} <b>{filter_name.title()}{urgent_emoji}:</b> {total_cars} машин\n"

                if success:
                    total_reports += 1
                    if is_urgent:
                        urgent_count += 1
                    quick_rec = summary.get("quick_recommendation", "")
                    if quick_rec:
                        rec_short = quick_rec[:60] + "..." if len(quick_rec) > 60 else quick_rec
                        message += f"   💡 {rec_short}\n"

                message += "\n"

            message += f"📄 <b>Создано HTML отчетов:</b> {total_reports}\n"
            if urgent_count > 0:
                message += f"🔥 <b>Urgent отчетов:</b> {urgent_count}\n"
            message += "<i>🤖 Файлы отправлены отдельными сообщениями</i>"

            await self.bot.send_message(
                chat_id=settings.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )

            logger.info(
                f"✅ Сводка анализа отправлена: {len(summaries)} фильтров, {total_reports} отчетов, {urgent_count} urgent")

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

    async def send_error_notification(self, error_text: str):
        """Отправляет уведомление об ошибке (public метод)"""
        await self._send_error_notification(error_text)

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

    def _format_car_message(self, car: Car, urgent: bool = False, urgent_filter: bool = False) -> str:
        """Форматирует сообщение о новой машине"""

        # Определяем заголовок в зависимости от urgent статуса
        if urgent and urgent_filter:
            header = "🔥🔥 <b>DOUBLE URGENT!</b> "
        elif urgent_filter:
            header = "🔥 <b>URGENT ФИЛЬТР!</b> "
        elif urgent:
            header = "🔥 <b>СРОЧНО!</b> "
        else:
            header = ""

        filter_suffix = f" (фильтр: {car.filter_name})" if urgent_filter else ""

        return f"""
{header}🚗 <b>Новое объявление - {car.brand}</b>{filter_suffix}

📝 <b>Заголовок:</b> {car.title}
💰 <b>Цена:</b> {car.price}
📅 <b>Год:</b> {car.year or 'нет данных'}
🛣 <b>Пробег:</b> {f"{car.mileage:,} км" if car.mileage else 'нет данных'}
📍 <b>Место:</b> {car.place}
📆 <b>Дата публикации:</b> {car.date_posted}

🔗 <a href="{car.link}">Посмотреть объявление</a>

⚙️ <b>Характеристики:</b> {car.features}

📝 <b>Описание:</b> {car.description or 'нет описания'}
        """.strip()

    async def close(self):
        """Закрытие сессии Telegram бота"""
        try:
            if hasattr(self.bot, 'session') and self.bot.session:
                await self.bot.session.close()
                logger.info("✅ Telegram bot session закрыта")
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия Telegram session: {e}")

    # 🆕 МЕТОДЫ ДЛЯ УВЕДОМЛЕНИЙ ОБ ИЗМЕНЕНИЯХ

        async def send_car_changes_notification(self, car, changes: Dict[str, Any]):
            """🔄 Отправляет уведомление об изменениях в объявлении"""
            logger.info(f"📱 send_car_changes_notification() called for car {car.id}")

            try:
                price_changed = changes.get("price_changed", False)
                description_changed = changes.get("description_changed", False)

                logger.info(
                    f"📊 Changes summary for car {car.id}: price={price_changed}, description={description_changed}")

                # Определяем тип изменения для заголовка
                if price_changed and description_changed:
                    header = "🔄💰📝 <b>ИЗМЕНЕНИЯ В ОБЪЯВЛЕНИИ</b>"
                elif price_changed:
                    header = "🔄💰 <b>ИЗМЕНЕНИЕ ЦЕНЫ</b>"
                elif description_changed:
                    header = "🔄📝 <b>ИЗМЕНЕНИЕ ОПИСАНИЯ</b>"
                else:
                    logger.warning(f"⚠️ No changes detected for car {car.id} - skipping notification")
                    return  # Нет изменений

                message = f"""{header}

    🚗 <b>Автомобиль:</b> {car.brand} {car.year or ''}
    📝 <b>Название:</b> {car.title[:60]}{'...' if len(car.title) > 60 else ''}
    🆔 <b>ID:</b> {car.id}

    """

                # Добавляем информацию об изменении цены
                if price_changed:
                    old_price = changes.get("old_price", "неизвестно")
                    new_price = changes.get("new_price", "неизвестно")

                    logger.info(f"💰 Price change details for car {car.id}: '{old_price}' → '{new_price}'")

                    # Определяем направление изменения цены
                    price_direction = self._analyze_price_change(old_price, new_price)

                    message += f"""💰 <b>ИЗМЕНЕНИЕ ЦЕНЫ:</b>
    📊 Было: {old_price}
    📊 Стало: {new_price}
    {price_direction}

    """

                # Добавляем информацию об изменении описания
                if description_changed:
                    old_desc = changes.get("old_description", "")
                    new_desc = changes.get("new_description", "")

                    logger.info(f"📝 Description change details for car {car.id}: "
                                f"{len(old_desc)} chars → {len(new_desc)} chars")

                    # Показываем первые 100 символов старого и нового описания
                    old_desc_short = (old_desc[:100] + "...") if len(old_desc) > 100 else old_desc
                    new_desc_short = (new_desc[:100] + "...") if len(new_desc) > 100 else new_desc

                    message += f"""📝 <b>ИЗМЕНЕНИЕ ОПИСАНИЯ:</b>
    📄 Было: "{old_desc_short or 'пустое'}"
    📄 Стало: "{new_desc_short or 'пустое'}"

    """

                message += f"""🔗 <a href="{car.link}">Посмотреть объявление</a>

    ⏰ <i>Проверка изменений: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"""

                logger.debug(f"📱 Sending change notification message for car {car.id} ({len(message)} chars)")

                await self.bot.send_message(
                    chat_id=settings.telegram_chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )

                logger.info(f"✅ Changes notification sent successfully for car {car.id}")

            except Exception as e:
                logger.error(f"❌ Error sending changes notification for car {car.id}: {str(e)}")
                logger.debug(f"🔍 Exception details: {type(e).__name__}: {str(e)}")

        async def send_daily_changes_summary(self, summary: Dict[str, Any]):
            """📊 Отправляет ежедневную сводку изменений"""
            logger.info("📊 send_daily_changes_summary() called")

            try:
                total_checked = summary.get("total_checked", 0)
                total_changes = summary.get("total_changes", 0)
                price_changes = summary.get("price_changes", 0)
                description_changes = summary.get("description_changes", 0)
                unavailable_count = summary.get("unavailable_count", 0)
                error_count = summary.get("error_count", 0)
                elapsed_seconds = summary.get("elapsed_seconds", 0)

                logger.info(f"📊 Summary stats: {total_checked} checked, {total_changes} changes, "
                            f"{price_changes} price, {description_changes} desc, "
                            f"{unavailable_count} unavailable, {error_count} errors, {elapsed_seconds:.1f}s")

                if total_changes == 0 and unavailable_count == 0 and error_count == 0:
                    # Если изменений нет, отправляем краткую сводку
                    message = f"""📊 <b>Ежедневная проверка изменений</b>

    ✅ Проверено: {total_checked} объявлений
    😴 Изменений не найдено
    ❌ Недоступных: {unavailable_count}
    ⏱️ Время: {elapsed_seconds:.1f}с

    ⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"""
                    logger.info("📱 Sending brief summary (no changes)")
                else:
                    # Подробная сводка с изменениями
                    message = f"""📊 <b>ЕЖЕДНЕВНАЯ СВОДКА ИЗМЕНЕНИЙ</b>

    🔍 <b>Проверено объявлений:</b> {total_checked}
    🔄 <b>Найдено изменений:</b> {total_changes}

    """
                    if price_changes > 0:
                        message += f"💰 Изменения цен: {price_changes}\n"
                    if description_changes > 0:
                        message += f"📝 Изменения описаний: {description_changes}\n"
                    if unavailable_count > 0:
                        message += f"❌ Недоступных/проданных: {unavailable_count}\n"
                    if error_count > 0:
                        message += f"⚠️ Ошибок при проверке: {error_count}\n"

                    success_rate = ((total_checked - error_count) / total_checked * 100) if total_checked > 0 else 0
                    message += f"""
    📈 <b>Эффективность:</b> {success_rate:.1f}% успешных проверок
    ⏱️ <b>Время выполнения:</b> {elapsed_seconds:.1f} секунд

    ⏰ <i>Следующая проверка: завтра в то же время</i>
    🕐 <i>Время проверки: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"""
                    logger.info("📱 Sending detailed summary (with changes)")

                await self.bot.send_message(
                    chat_id=settings.telegram_chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML
                )

                logger.info(
                    f"✅ Daily changes summary sent successfully: {total_changes} changes in {total_checked} cars")

            except Exception as e:
                logger.error(f"❌ Error sending daily changes summary: {str(e)}")
                logger.debug(f"🔍 Exception details: {type(e).__name__}: {str(e)}")

        async def send_price_drops_alert(self, cars_with_drops: List, min_drop: int):
            """💸 Отправляет уведомление о значительных падениях цен"""
            if not cars_with_drops:
                return

            try:
                message = f"""💸💸 <b>ЗНАЧИТЕЛЬНЫЕ ПАДЕНИЯ ЦЕН!</b> 💸💸

    🎯 Найдено {len(cars_with_drops)} объявлений со снижением цены на {min_drop}€+

    """

                for i, car in enumerate(cars_with_drops[:5], 1):  # Показываем топ-5
                    old_price_num = self._extract_price_number(car.previous_price)
                    new_price_num = self._extract_price_number(car.price)

                    if old_price_num and new_price_num:
                        drop_amount = old_price_num - new_price_num
                        drop_percent = (drop_amount / old_price_num) * 100

                        message += f"""<b>{i}. {car.brand} {car.year or ''}</b>
    📝 {car.title[:50]}{'...' if len(car.title) > 50 else ''}
    💰 Было: {car.previous_price} → Стало: {car.price}
    📉 Снижение: -{drop_amount:,}€ ({drop_percent:.1f}%)
    🔗 <a href="{car.link}">Посмотреть</a>

    """

                if len(cars_with_drops) > 5:
                    message += f"<i>... и еще {len(cars_with_drops) - 5} объявлений</i>\n\n"

                message += "🏃‍♂️ <i>Возможно, срочная продажа или торг!</i>"

                await self.bot.send_message(
                    chat_id=settings.telegram_chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )

                logger.info(f"🚨 Price drops alert sent: {len(cars_with_drops)} cars with significant drops")

            except Exception as e:
                logger.error(f"❌ Error sending price drops alert: {e}")

        def _analyze_price_change(self, old_price: str, new_price: str) -> str:
            """Анализирует изменение цены и возвращает эмодзи + описание"""
            try:
                old_num = self._extract_price_number(old_price)
                new_num = self._extract_price_number(new_price)

                if not old_num or not new_num:
                    return "🔄 Изменение цены"

                diff = new_num - old_num
                percent_change = (diff / old_num) * 100

                if diff > 0:
                    if percent_change > 10:
                        return f"📈 Значительное повышение (+{diff:,}€, +{percent_change:.1f}%)"
                    else:
                        return f"📈 Повышение (+{diff:,}€, +{percent_change:.1f}%)"
                elif diff < 0:
                    if abs(percent_change) > 10:
                        return f"📉 Значительное снижение ({diff:,}€, {percent_change:.1f}%) 🎯"
                    else:
                        return f"📉 Снижение ({diff:,}€, {percent_change:.1f}%)"
                else:
                    return "🔄 Цена не изменилась (возможно, формат)"

            except Exception:
                return "🔄 Изменение цены"

        def _extract_price_number(self, price_text: str) -> Optional[int]:
            """Извлекает число из текста цены"""
            import re
            if not price_text:
                return None

            # Убираем все кроме цифр
            numbers = re.findall(r'\d+', price_text.replace(',', '').replace(' ', ''))
            if numbers:
                try:
                    return int(''.join(numbers))
                except:
                    return None
            return None
