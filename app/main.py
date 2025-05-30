# app/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import init_db
from app.api.cars import router as cars_router
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
    title="Car Monitor Bot",
    description="Telegram bot для мониторинга автомобилей на Bazaraki",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(cars_router)


@app.get("/")
async def root():
    return {"message": "Car Monitor Bot работает"}


@app.get("/health")
async def health():
    return {"status": "OK"}