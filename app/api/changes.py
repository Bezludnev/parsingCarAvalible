# app/api/changes.py - API для отслеживания изменений
from fastapi import APIRouter, HTTPException, Query
from app.services.changes_service import ChangesTrackingService
from app.repository.car_repository import CarRepository
from app.database import async_session
from typing import List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/changes", tags=["Changes Tracking"])


@router.post("/check-all")
async def trigger_full_changes_check():
    """🔄 Запуск полной проверки изменений всех машин"""
    logger.info("🔄 API trigger_full_changes_check() called")

    try:
        service = ChangesTrackingService()
        logger.info("🚀 Starting full changes check via API...")

        await service.check_all_cars_for_changes()

        logger.info("✅ API trigger_full_changes_check() completed successfully")

        return {
            "status": "success",
            "message": "Полная проверка изменений запущена и завершена",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ API trigger_full_changes_check() error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.post("/check-cars")
async def check_specific_cars(car_ids: List[int]):
    """🎯 Проверка изменений конкретных машин"""
    logger.info(f"🎯 API check_specific_cars() called with {len(car_ids)} car IDs: {car_ids}")

    try:
        if not car_ids:
            logger.warning("❌ Empty car_ids list provided")
            raise HTTPException(status_code=400, detail="Список car_ids не может быть пустым")

        if len(car_ids) > 50:
            logger.warning(f"❌ Too many car IDs: {len(car_ids)} (max 50)")
            raise HTTPException(status_code=400, detail="Максимум 50 машин за раз")

        service = ChangesTrackingService()
        logger.info(f"🚀 Starting specific cars check for IDs: {car_ids}")

        result = await service.check_specific_cars_changes(car_ids)

        changes_count = sum(1 for r in result.get("results", []) if r.get("has_changes"))
        logger.info(f"✅ API check_specific_cars() completed: {changes_count} changes found")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API check_specific_cars() error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.get("/summary")
async def get_changes_summary(days: int = Query(default=7, ge=1, le=30)):
    """📊 Сводка изменений за последние дни"""
    logger.info(f"📊 API get_changes_summary() called for {days} days")

    try:
        service = ChangesTrackingService()
        summary = await service.get_recent_changes_summary(days)

        logger.info(f"✅ API get_changes_summary() completed for {days} days")

        return {
            "status": "success",
            "period_days": days,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ API get_changes_summary() error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.get("/recent-price-changes")
async def get_recent_price_changes(days: int = Query(default=7, ge=1, le=30)):
    """💰 Получить машины с недавними изменениями цен"""
    try:
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_recent_price_changes(days)

            result = []
            for car in cars:
                result.append({
                    "id": car.id,
                    "title": car.title,
                    "brand": car.brand,
                    "year": car.year,
                    "current_price": car.price,
                    "previous_price": car.previous_price,
                    "price_changed_at": car.price_changed_at.isoformat() if car.price_changed_at else None,
                    "price_changes_count": car.price_changes_count,
                    "link": car.link
                })

            return {
                "status": "success",
                "period_days": days,
                "price_changes_count": len(result),
                "cars": result
            }
    except Exception as e:
        logger.error(f"❌ Error getting recent price changes: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.get("/recent-description-changes")
async def get_recent_description_changes(days: int = Query(default=7, ge=1, le=30)):
    """📝 Получить машины с недавними изменениями описаний"""
    try:
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_recent_description_changes(days)

            result = []
            for car in cars:
                result.append({
                    "id": car.id,
                    "title": car.title,
                    "brand": car.brand,
                    "year": car.year,
                    "current_description": (car.description or "")[:200] + (
                        "..." if len(car.description or "") > 200 else ""),
                    "previous_description": (car.previous_description or "")[:200] + (
                        "..." if len(car.previous_description or "") > 200 else ""),
                    "description_changed_at": car.description_changed_at.isoformat() if car.description_changed_at else None,
                    "description_changes_count": car.description_changes_count,
                    "link": car.link
                })

            return {
                "status": "success",
                "period_days": days,
                "description_changes_count": len(result),
                "cars": result
            }
    except Exception as e:
        logger.error(f"❌ Error getting recent description changes: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.get("/price-drops")
async def get_significant_price_drops(
        days: int = Query(default=7, ge=1, le=30),
        min_drop_euros: int = Query(default=500, ge=100, le=10000)
):
    """💸 Получить машины со значительными падениями цен"""
    try:
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_cars_with_price_drops(days, min_drop_euros)

            result = []
            for car in cars:
                old_price_num = repo._extract_price_number(car.previous_price)
                new_price_num = repo._extract_price_number(car.price)

                if old_price_num and new_price_num:
                    drop_amount = old_price_num - new_price_num
                    drop_percent = (drop_amount / old_price_num) * 100

                    result.append({
                        "id": car.id,
                        "title": car.title,
                        "brand": car.brand,
                        "year": car.year,
                        "current_price": car.price,
                        "previous_price": car.previous_price,
                        "drop_amount_euros": drop_amount,
                        "drop_percentage": round(drop_percent, 1),
                        "price_changed_at": car.price_changed_at.isoformat() if car.price_changed_at else None,
                        "link": car.link
                    })

            # Сортируем по размеру падения
            result.sort(key=lambda x: x["drop_amount_euros"], reverse=True)

            return {
                "status": "success",
                "period_days": days,
                "min_drop_euros": min_drop_euros,
                "significant_drops_count": len(result),
                "cars": result
            }
    except Exception as e:
        logger.error(f"❌ Error getting price drops: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.post("/price-drops-alert")
async def send_price_drops_alert(
        days: int = Query(default=7, ge=1, le=30),
        min_drop_euros: int = Query(default=1000, ge=100, le=10000)
):
    """💸 Отправить уведомление о падениях цен в Telegram"""
    try:
        async with async_session() as session:
            repo = CarRepository(session)
            cars_with_drops = await repo.get_cars_with_price_drops(days, min_drop_euros)

            if cars_with_drops:
                service = ChangesTrackingService()
                await service.telegram.send_price_drops_alert(cars_with_drops, min_drop_euros)

                return {
                    "status": "success",
                    "message": f"Уведомление отправлено: {len(cars_with_drops)} машин со снижением на {min_drop_euros}€+",
                    "cars_count": len(cars_with_drops),
                    "period_days": days
                }
            else:
                return {
                    "status": "success",
                    "message": f"Не найдено машин со снижением цены на {min_drop_euros}€+ за {days} дней",
                    "cars_count": 0,
                    "period_days": days
                }
    except Exception as e:
        logger.error(f"❌ Error sending price drops alert: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.get("/never-checked")
async def get_never_checked_cars(limit: int = Query(default=50, ge=1, le=200)):
    """🔍 Получить машины которые ни разу не проверялись на изменения"""
    try:
        async with async_session() as session:
            repo = CarRepository(session)
            cars = await repo.get_cars_never_checked(limit)

            result = []
            for car in cars:
                result.append({
                    "id": car.id,
                    "title": car.title,
                    "brand": car.brand,
                    "year": car.year,
                    "price": car.price,
                    "created_at": car.created_at.isoformat() if car.created_at else None,
                    "link": car.link
                })

            return {
                "status": "success",
                "never_checked_count": len(result),
                "cars": result
            }
    except Exception as e:
        logger.error(f"❌ Error getting never checked cars: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.get("/status")
async def get_changes_tracking_status():
    """📊 Статус системы отслеживания изменений"""
    try:
        async with async_session() as session:
            repo = CarRepository(session)

            # Получаем статистику
            never_checked = await repo.get_cars_never_checked(1000)  # Максимум для подсчета
            recent_changes = await repo.get_changes_summary(7)

            from datetime import datetime, timedelta
            cutoff_24h = datetime.now() - timedelta(hours=24)
            recent_checked = await repo.get_cars_for_changes_check(cutoff_24h, 1000)

            return {
                "status": "operational",
                "features": [
                    "daily_changes_check",
                    "price_tracking",
                    "description_tracking",
                    "price_drops_alerts",
                    "telegram_notifications"
                ],
                "statistics": {
                    "never_checked_count": len(never_checked),
                    "needs_check_24h": len(recent_checked),
                    "recent_changes_7d": recent_changes
                },
                "schedule": {
                    "daily_check": "14:30 (Cyprus time)",
                    "weekly_price_drops": "Sunday 10:00"
                }
            }
    except Exception as e:
        logger.error(f"❌ Error getting changes tracking status: {e}")
        return {
            "status": "error",
            "error": str(e)
        }