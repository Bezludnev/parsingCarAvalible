# app/main.py - ОБНОВЛЕННАЯ с reports router
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import init_db
from app.api.cars import router as cars_router
from app.api.analysis import router as analysis_router
from app.api.reports import router as reports_router  # НОВЫЙ
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("База данных инициализирована")

    # Schedule monitoring with random interval (5-10 min) and night pause
    scheduler.add_job(
        check_cars_with_night_pause,
        'interval',
        minutes=7.5,  # базовый интервал
        jitter=150,  # ±2.5 минуты в секундах (итого 5-10 мин)
        id='car_monitor'
    )
    scheduler.start()
    logger.info("Scheduler запущен (проверка каждые 5-10 минут, ночью не работает)")

    yield

    # Shutdown
    scheduler.shutdown()
    await monitor_service.telegram.close()


app = FastAPI(
    title="Car Monitor Bot with AI Analysis & HTML Reports",
    description="Telegram bot для мониторинга автомобилей на Bazaraki с AI анализом и HTML отчетами",
    version="2.1.0",
    lifespan=lifespan
)

# Подключаем роутеры
app.include_router(cars_router)
app.include_router(analysis_router)
app.include_router(reports_router)  # НОВЫЙ


@app.get("/")
async def root():
    return {
        "message": "Car Monitor Bot with AI Analysis & HTML Reports работает",
        "version": "2.1.0",
        "features": [
            "monitoring",
            "ai_analysis",
            "telegram_notifications",
            "html_reports"
        ]
    }


@app.get("/health")
async def health():
    return {
        "status": "OK",
        "features": [
            "monitoring",
            "ai_analysis",
            "telegram_notifications",
            "html_reports",
            "file_downloads"
        ],
        "endpoints": {
            "cars": "/cars",
            "analysis": "/analysis",
            "reports": "/reports"
        }
    }