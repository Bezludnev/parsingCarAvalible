# app/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import init_db
from app.api.cars import router as cars_router
from app.services.monitor_service import MonitorService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global scheduler
scheduler = AsyncIOScheduler()
monitor_service = MonitorService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("База данных инициализирована")

    # Schedule monitoring every 30 minutes
    scheduler.add_job(
        monitor_service.check_new_cars,
        'interval',
        minutes=30,
        id='car_monitor'
    )
    scheduler.start()
    logger.info("Scheduler запущен (проверка каждые 30 минут)")

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