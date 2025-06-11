# app/main.py - ОБНОВЛЕННАЯ с ежедневной проверкой изменений
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import init_db
from app.api.cars import router as cars_router
from app.api.analysis import router as analysis_router
from app.api.reports import router as reports_router
from app.services.monitor_service import MonitorService
from app.services.changes_service import ChangesTrackingService
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global scheduler and services
scheduler = AsyncIOScheduler()
monitor_service = MonitorService()
changes_service = ChangesTrackingService()


async def check_cars_with_night_pause():
    """Проверка новых машин с учетом ночного времени"""
    current_hour = datetime.now().hour

    if 2 <= current_hour < 6:
        logger.info("😴 Ночное время (02:00-06:00) - пропускаем проверку новых машин")
        return

    logger.info("🔍 Запуск проверки новых машин...")
    await monitor_service.check_new_cars()


async def scheduled_ai_analysis():
    """🤖 Запланированный AI анализ базы данных 2 раза в день"""
    try:
        current_time = datetime.now().strftime("%H:%M")
        logger.info(f"🤖 Запуск запланированного AI анализа в {current_time}")

        from app.services.analysis_service import AnalysisService
        from app.services.telegram_service import TelegramService

        analysis_service = AnalysisService()
        telegram_service = TelegramService()

        # Полный анализ рынка для выявления лучших вариантов
        result = await analysis_service.analyze_full_database(min_cars_per_brand=3)

        if result.get("success"):
            # Отправляем результат в Telegram с пометкой о scheduled анализе
            await telegram_service.send_scheduled_analysis_report(result)

            # Если есть рекомендованные машины - отправляем отдельное уведомление
            recommended_ids = result.get("recommended_car_ids", [])
            if recommended_ids:
                await telegram_service.send_top_deals_notification(result, recommended_ids)

            logger.info(f"✅ Scheduled AI анализ завершен: {result.get('total_cars_analyzed', 0)} машин, "
                        f"{len(recommended_ids)} рекомендаций")
        else:
            logger.error(f"❌ Scheduled AI анализ не удался: {result.get('error')}")

    except Exception as e:
        logger.error(f"❌ Ошибка scheduled AI анализа: {e}")
        # Отправляем уведомление об ошибке
        try:
            telegram_service = TelegramService()
            await telegram_service.send_error_notification(f"Scheduled AI анализ не удался: {str(e)}")
        except:
            pass


async def daily_changes_check():
    """🔄 Ежедневная проверка изменений в объявлениях"""
    try:
        current_time = datetime.now().strftime("%H:%M")
        logger.info(f"🔄 Запуск ежедневной проверки изменений в {current_time}")

        await changes_service.check_all_cars_for_changes()

        logger.info("✅ Ежедневная проверка изменений завершена")

    except Exception as e:
        logger.error(f"❌ Ошибка ежедневной проверки изменений: {e}")
        # Отправляем уведомление об ошибке
        try:
            from app.services.telegram_service import TelegramService
            telegram_service = TelegramService()
            await telegram_service.send_error_notification(f"Проверка изменений не удалась: {str(e)}")
        except:
            pass


async def weekly_price_drops_check():
    """💸 Еженедельная проверка значительных падений цен"""
    try:
        logger.info("💸 Запуск еженедельной проверки падений цен...")

        from app.repository.car_repository import CarRepository
        from app.database import async_session

        async with async_session() as session:
            repo = CarRepository(session)
            cars_with_drops = await repo.get_cars_with_price_drops(days=7, min_drop_euros=1000)

            if cars_with_drops:
                await changes_service.telegram.send_price_drops_alert(cars_with_drops, 1000)
                logger.info(f"✅ Найдено {len(cars_with_drops)} машин со значительным падением цен")
            else:
                logger.info("💸 Значительных падений цен не найдено")

    except Exception as e:
        logger.error(f"❌ Ошибка проверки падений цен: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("🗄️ База данных инициализирована")

    # 🔍 Schedule monitoring with random interval (5-10 min) and night pause
    scheduler.add_job(
        check_cars_with_night_pause,
        'interval',
        minutes=35,  # базовый интервал
        jitter=300,  # ±2.5 минуты в секундах (итого 5-10 мин)
        id='car_monitor'
    )

    # 🤖 AI анализ базы данных 2 раза в день
    scheduler.add_job(
        scheduled_ai_analysis,
        'cron',
        hour='9,18',  # 09:00 и 18:00
        minute=0,
        id='scheduled_ai_analysis',
        timezone='Europe/Nicosia'  # Кипрское время
    )

    # 🔄 НОВОЕ: Ежедневная проверка изменений в объявлениях
    scheduler.add_job(
        daily_changes_check,
        'cron',
        hour=14,  # 14:00 по времени Кипра
        minute=30,
        id='daily_changes_check',
        timezone='Europe/Nicosia'
    )

    # 💸 НОВОЕ: Еженедельная проверка падений цен
    scheduler.add_job(
        weekly_price_drops_check,
        'cron',
        day_of_week='sun',  # Каждое воскресенье
        hour=10,
        minute=0,
        id='weekly_price_drops_check',
        timezone='Europe/Nicosia'
    )

    scheduler.start()
    logger.info("⏰ Scheduler запущен:")
    logger.info("  - 🔍 Мониторинг новых машин: каждые 5-10 минут (ночью не работает)")
    logger.info("  - 🤖 AI анализ: 09:00 и 18:00 по времени Кипра")
    logger.info("  - 🔄 Проверка изменений: 14:30 ежедневно")
    logger.info("  - 💸 Проверка падений цен: воскресенье 10:00")

    yield

    # Shutdown
    scheduler.shutdown()
    await monitor_service.telegram.close()


app = FastAPI(
    title="Car Monitor Bot with Changes Tracking",
    description="Telegram бот для мониторинга автомобилей на Bazaraki с отслеживанием изменений цен и описаний",
    version="2.3.0",
    lifespan=lifespan
)

# Подключаем роутеры
app.include_router(cars_router)
app.include_router(analysis_router)
app.include_router(reports_router)

# 🆕 Новый роутер для отслеживания изменений
from app.api.changes import router as changes_router

app.include_router(changes_router)


# 🆕 Новые endpoints для отслеживания изменений
@app.post("/changes/check-all")
async def trigger_changes_check():
    """🔄 Ручной запуск проверки изменений всех машин"""
    await changes_service.check_all_cars_for_changes()
    return {"message": "Проверка изменений запущена"}


@app.post("/changes/check-cars")
async def check_specific_cars_changes(car_ids: list[int]):
    """🎯 Проверка изменений конкретных машин"""
    result = await changes_service.check_specific_cars_changes(car_ids)
    return result


@app.get("/changes/summary")
async def get_recent_changes_summary(days: int = 7):
    """📊 Сводка изменений за последние дни"""
    result = await changes_service.get_recent_changes_summary(days)
    return result


@app.post("/changes/price-drops-alert")
async def trigger_price_drops_alert(days: int = 7, min_drop: int = 1000):
    """💸 Ручной запуск проверки падений цен"""
    from app.repository.car_repository import CarRepository
    from app.database import async_session

    async with async_session() as session:
        repo = CarRepository(session)
        cars_with_drops = await repo.get_cars_with_price_drops(days, min_drop)

        if cars_with_drops:
            await changes_service.telegram.send_price_drops_alert(cars_with_drops, min_drop)
            return {
                "message": f"Найдено {len(cars_with_drops)} машин со снижением цены на {min_drop}€+",
                "cars_count": len(cars_with_drops)
            }
        else:
            return {
                "message": f"Не найдено машин со снижением цены на {min_drop}€+ за {days} дней",
                "cars_count": 0
            }


@app.get("/")
async def root():
    return {
        "message": "Car Monitor Bot with Changes Tracking работает",
        "version": "2.3.0",
        "features": [
            "monitoring",
            "scheduled_ai_analysis",
            "changes_tracking",
            "price_drops_alerts",
            "telegram_notifications",
            "html_reports"
        ],
        "schedule": {
            "monitoring": "каждые 5-10 минут (пауза ночью)",
            "ai_analysis": "09:00 и 18:00 (поиск лучших сделок)",
            "changes_check": "14:30 ежедневно",
            "price_drops_check": "воскресенье 10:00"
        }
    }


@app.get("/health")
async def health():
    return {
        "status": "OK",
        "features": [
            "monitoring",
            "scheduled_ai_analysis",
            "changes_tracking",
            "price_drops_alerts",
            "telegram_notifications",
            "html_reports",
            "database_analysis"
        ],
        "endpoints": {
            "cars": "/cars",
            "analysis": "/analysis",
            "reports": "/reports",
            "changes": "/changes"
        },
        "schedule": {
            "monitoring": "каждые 5-10 минут",
            "ai_analysis": "каждый день 2 раза (09:00, 18:00)",
            "changes_check": "каждый день (14:30)",
            "price_drops": "каждую неделю (вс 10:00)"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)