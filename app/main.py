# app/main.py - ОБНОВЛЕННАЯ с scheduled AI анализом
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import init_db
from app.api.cars import router as cars_router
from app.api.analysis import router as analysis_router
from app.api.reports import router as reports_router
from app.services.monitor_service import MonitorService
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global scheduler
scheduler = AsyncIOScheduler()
monitor_service = MonitorService()


async def check_cars_with_night_pause():
    """Проверка с учетом ночного времени"""
    current_hour = datetime.now().hour

    if 2 <= current_hour < 6:
        logger.info("Ночное время (02:00-06:00) - пропускаем проверку")
        return

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("База данных инициализирована")

    # Schedule monitoring with random interval (5-10 min) and night pause
    scheduler.add_job(
        check_cars_with_night_pause,
        'interval',
        minutes=35,  # базовый интервал
        jitter=300,  # ±2.5 минуты в секундах (итого 5-10 мин)
        id='car_monitor'
    )

    # 🤖 НОВОЕ: AI анализ базы данных 2 раза в день
    scheduler.add_job(
        scheduled_ai_analysis,
        'cron',
        hour='9,18',  # 09:00 и 18:00
        minute=0,
        id='scheduled_ai_analysis',
        timezone='Europe/Nicosia'  # Кипрское время
    )

    scheduler.start()
    logger.info("Scheduler запущен:")
    logger.info("  - Мониторинг: каждые 5-10 минут (ночью не работает)")
    logger.info("  - AI анализ: 09:00 и 18:00 по времени Кипра")

    yield

    # Shutdown
    scheduler.shutdown()
    await monitor_service.telegram.close()


app = FastAPI(
    title="Car Monitor Bot with Scheduled AI Analysis",
    description="Telegram бот для мониторинга автомобилей на Bazaraki с автоматическим AI анализом 2 раза в день",
    version="2.2.0",
    lifespan=lifespan
)

# Подключаем роутеры
app.include_router(cars_router)
app.include_router(analysis_router)
app.include_router(reports_router)


@app.get("/")
async def root():
    return {
        "message": "Car Monitor Bot with Scheduled AI Analysis работает",
        "version": "2.2.0",
        "features": [
            "monitoring",
            "scheduled_ai_analysis",
            "telegram_notifications",
            "html_reports",
            "deal_hunting"
        ],
        "schedule": {
            "monitoring": "каждые 5-10 минут (пауза ночью)",
            "ai_analysis": "09:00 и 18:00 (поиск лучших сделок)"
        }
    }


@app.get("/health")
async def health():
    return {
        "status": "OK",
        "features": [
            "monitoring",
            "scheduled_ai_analysis",
            "telegram_notifications",
            "html_reports",
            "file_downloads",
            "deal_hunting",
            "database_analysis"
        ],
        "endpoints": {
            "cars": "/cars",
            "analysis": "/analysis",
            "reports": "/reports"
        },
        "schedule": {
            "monitoring": "каждые 5-10 минут",
            "ai_analysis": "каждый день 2 раза (09:00, 18:00)"
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)