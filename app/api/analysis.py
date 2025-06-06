# app/api/analysis.py - С SCHEDULED ENDPOINTS
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from app.services.analysis_service import AnalysisService
from app.schemas.analysis import (
    AnalysisResponse,
    ComparisonRequest,
    RecentCarsRequest,
    QuickAnalysisResponse
)
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["AI Analysis"])


# 🤖 НОВЫЕ SCHEDULED ENDPOINTS

@router.post("/scheduled-analysis")
async def trigger_scheduled_analysis():
    """🤖 Ручной запуск scheduled AI анализа (как если бы он был по расписанию)"""
    try:
        from app.services.analysis_service import AnalysisService
        from app.services.telegram_service import TelegramService

        analysis_service = AnalysisService()
        telegram_service = TelegramService()

        # Полный анализ базы данных
        result = await analysis_service.analyze_full_database(min_cars_per_brand=3)

        if not result.get("success", True):
            raise HTTPException(status_code=404, detail=result.get("error", "Ошибка анализа"))

        # Отправляем как scheduled анализ
        await telegram_service.send_scheduled_analysis_report(result)

        # Если есть рекомендации - отправляем топ предложения
        recommended_ids = result.get("recommended_car_ids", [])
        if recommended_ids:
            await telegram_service.send_top_deals_notification(result, recommended_ids)

        return {
            "status": "success",
            "analysis_type": "scheduled_manual",
            "cars_analyzed": result.get("total_cars_analyzed", 0),
            "brands_analyzed": len(result.get("brands_analyzed", [])),
            "recommendations": len(recommended_ids),
            "message": "Manual scheduled анализ выполнен и отправлен в Telegram"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Manual scheduled analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка manual scheduled анализа: {str(e)}")


@router.get("/scheduler-status")
async def get_scheduler_status():
    """⏰ Статус планировщика AI анализа"""
    try:
        from app.main import scheduler

        jobs = []
        for job in scheduler.get_jobs():
            next_run = job.next_run_time.strftime("%d.%m.%Y %H:%M:%S") if job.next_run_time else "не запланирован"
            jobs.append({
                "id": job.id,
                "name": job.name or job.id,
                "next_run": next_run,
                "trigger": str(job.trigger)
            })

        # Информация о scheduled AI анализе
        ai_job = next((job for job in jobs if "ai_analysis" in job["id"]), None)

        return {
            "scheduler_running": scheduler.running,
            "all_jobs": jobs,
            "ai_analysis_job": ai_job,
            "timezone": "Europe/Nicosia",
            "schedule": "09:00 и 18:00 по времени Кипра",
            "current_time": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "status": "operational" if ai_job else "no_ai_job"
        }

    except Exception as e:
        logger.error(f"❌ Scheduler status error: {e}")
        return {
            "scheduler_running": False,
            "error": str(e),
            "status": "error"
        }


# 🎯 ОСНОВНЫЕ ENDPOINTS ДЛЯ АНАЛИЗА БАЗЫ

@router.post("/full-market", response_model=AnalysisResponse)
async def analyze_full_market(
        min_cars_per_brand: int = Query(default=5, ge=1, le=50, description="Минимум машин на бренд"),
        background_tasks: BackgroundTasks = None
):
    """🎯 ГЛАВНЫЙ: Полный анализ всего рынка через o3-mini (экономия токенов!)"""
    try:
        service = AnalysisService()
        result = await service.analyze_full_database(min_cars_per_brand)

        if not result.get("success", True):
            raise HTTPException(status_code=404, detail=result.get("error", "Ошибка анализа"))

        # В фоне отправляем в Telegram
        if background_tasks:
            background_tasks.add_task(_send_to_telegram_bg, result, "full_market")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Full market analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка полного анализа рынка: {str(e)}")


@router.post("/market-trends", response_model=AnalysisResponse)
async def analyze_market_trends(
        days: int = Query(default=14, ge=7, le=60, description="Период для анализа трендов"),
        background_tasks: BackgroundTasks = None
):
    """📈 Анализ трендов рынка на основе всей базы данных"""
    try:
        service = AnalysisService()
        result = await service.analyze_recent_market_trends(days)

        if not result.get("success", True):
            raise HTTPException(status_code=404, detail=result.get("error", "Ошибка анализа трендов"))

        if background_tasks:
            background_tasks.add_task(_send_to_telegram_bg, result, "trends")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Market trends analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка анализа трендов: {str(e)}")


@router.get("/market-summary")
async def get_market_summary():
    """⚡ Быстрая сводка по всему рынку (без AI анализа)"""
    try:
        service = AnalysisService()
        result = await service.get_market_insights_summary()
        return result

    except Exception as e:
        logger.error(f"❌ Market summary error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения сводки: {str(e)}")


@router.post("/send-full-market-to-telegram")
async def send_full_market_analysis_to_telegram(
        min_cars_per_brand: int = Query(default=5, ge=1, le=50)
):
    """📱 Полный анализ рынка + отправка в Telegram"""
    try:
        service = AnalysisService()
        result = await service.analyze_full_database(min_cars_per_brand)

        if not result.get("success", True):
            raise HTTPException(status_code=404, detail=result.get("error", "Ошибка анализа"))

        # Отправляем в Telegram с HTML отчетом
        from app.services.telegram_service import TelegramService
        telegram = TelegramService()
        await telegram.send_ai_analysis_report(result, urgent_mode=False)

        return {
            "status": "sent_to_telegram",
            "analysis_type": "full_market",
            "cars_analyzed": result.get("total_cars_analyzed", 0),
            "brands_analyzed": len(result.get("brands_analyzed", [])),
            "message": "Полный анализ рынка отправлен в Telegram с HTML отчетом"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Send full market to Telegram error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка отправки анализа: {str(e)}")


@router.post("/send-trends-to-telegram")
async def send_trends_analysis_to_telegram(
        days: int = Query(default=14, ge=7, le=60)
):
    """📱 Анализ трендов + отправка в Telegram"""
    try:
        service = AnalysisService()
        result = await service.analyze_recent_market_trends(days)

        if not result.get("success", True):
            raise HTTPException(status_code=404, detail=result.get("error", "Ошибка анализа"))

        from app.services.telegram_service import TelegramService
        telegram = TelegramService()
        await telegram.send_ai_analysis_report(result, urgent_mode=False)

        return {
            "status": "sent_to_telegram",
            "analysis_type": "market_trends",
            "cars_analyzed": result.get("total_cars_analyzed", 0),
            "recent_cars": result.get("recent_cars_count", 0),
            "trends_period": days,
            "message": f"Анализ трендов за {days} дней отправлен в Telegram"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Send trends to Telegram error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка отправки трендов: {str(e)}")


# 📊 ENDPOINTS ДЛЯ МОНИТОРИНГА И СТАТИСТИКИ

@router.get("/database-stats")
async def get_database_statistics():
    """📊 Детальная статистика по всей базе данных"""
    try:
        from app.repository.car_repository import CarRepository
        from app.database import async_session

        async with async_session() as session:
            repo = CarRepository(session)

            global_stats = await repo.get_global_statistics()
            recent_stats = await repo.get_recent_statistics(7)
            brands_breakdown = await repo.get_brands_breakdown()
            filters_breakdown = await repo.get_filters_breakdown()
            price_ranges = await repo.get_price_ranges_analysis()
            year_distribution = await repo.get_year_distribution()
            daily_activity = await repo.get_market_activity_by_days(30)

            return {
                "status": "success",
                "global_statistics": global_stats,
                "recent_week_statistics": recent_stats,
                "brands_breakdown": brands_breakdown,
                "filters_breakdown": filters_breakdown,
                "price_ranges_analysis": price_ranges,
                "year_distribution": year_distribution,
                "daily_activity_last_30_days": daily_activity,
                "analysis_ready": global_stats.get("total_cars", 0) >= 20,
                "recommended_analysis": "full_market" if global_stats.get("total_cars", 0) >= 50 else "legacy"
            }

    except Exception as e:
        logger.error(f"❌ Database stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")


# 🔧 LEGACY ENDPOINTS (сохраняем для обратной совместимости)

@router.post("/by-filter/{filter_name}", response_model=AnalysisResponse)
async def analyze_by_filter(
        filter_name: str,
        limit: int = Query(default=20, ge=5, le=50)
):
    """🤖 AI анализ машин по фильтру (LEGACY - берет данные из базы)"""
    try:
        service = AnalysisService()
        result = await service.analyze_cars_by_filter(filter_name, limit)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Analysis error for filter {filter_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка AI анализа: {str(e)}")


@router.post("/compare", response_model=AnalysisResponse)
async def compare_cars(request: ComparisonRequest):
    """🆚 Сравнение конкретных машин через o3-mini"""
    try:
        service = AnalysisService()
        result = await service.compare_specific_cars(request.car_ids)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Comparison error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сравнения: {str(e)}")


@router.get("/quick/{filter_name}", response_model=QuickAnalysisResponse)
async def quick_analysis(filter_name: str):
    """⚡ Быстрый анализ через o3-mini без детального разбора"""
    try:
        service = AnalysisService()
        result = await service.get_quick_insight(filter_name)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Quick analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка быстрого анализа: {str(e)}")


@router.post("/manual-analysis")
async def trigger_manual_analysis(filter_name: str = Query(default=None, description="Конкретный фильтр или все")):
    """🔧 Ручной запуск AI анализа с отправкой в Telegram"""
    try:
        from app.services.monitor_service import MonitorService

        monitor = MonitorService()
        result = await monitor.run_manual_ai_analysis(filter_name)

        return result

    except Exception as e:
        logger.error(f"❌ Manual analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка ручного анализа: {str(e)}")


# 🔍 СИСТЕМНАЯ ИНФОРМАЦИЯ

@router.get("/status")
async def get_analysis_status():
    """📊 Статус сервиса анализа с o3-mini"""
    try:
        from app.services.openai_service import OpenAIService
        from app.repository.car_repository import CarRepository
        from app.database import async_session

        openai_service = OpenAIService()
        connection_test = await openai_service.test_connection()

        # Получаем статистику базы
        async with async_session() as session:
            repo = CarRepository(session)
            global_stats = await repo.get_global_statistics()

        cars_in_db = global_stats.get("total_cars", 0)
        analysis_ready = cars_in_db >= 20

        if connection_test.get("status") == "success":
            return {
                "status": "operational",
                "ai_service": "online",
                "model": "o3-mini",
                "database_cars": cars_in_db,
                "analysis_ready": analysis_ready,
                "recommended_endpoint": "/analysis/full-market" if analysis_ready else "/analysis/by-filter",
                "features": [
                    "scheduled_analysis",
                    "full_market_analysis",
                    "market_trends",
                    "database_statistics",
                    "filter_analysis",
                    "car_comparison",
                    "html_reports"
                ],
                "connection_test": "passed"
            }
        else:
            return {
                "status": "degraded",
                "ai_service": "limited",
                "model": "o3-mini",
                "database_cars": cars_in_db,
                "analysis_ready": False,
                "error": connection_test.get("error"),
                "connection_test": "failed"
            }

    except Exception as e:
        logger.error(f"❌ Status check failed: {e}")
        return {
            "status": "offline",
            "ai_service": "offline",
            "model": "o3-mini",
            "database_cars": 0,
            "analysis_ready": False,
            "error": str(e)
        }


@router.get("/models")
async def get_available_models():
    """🔧 Проверка доступных AI моделей"""
    try:
        from app.services.openai_service import OpenAIService

        openai_service = OpenAIService()
        models = await openai_service.get_available_models()

        return {
            "available_models": models,
            "current_model": "o3-mini",
            "total_models": len(models),
            "optimized_for": "full_database_analysis"
        }

    except Exception as e:
        logger.error(f"❌ Models check failed: {e}")
        return {
            "available_models": ["o3-mini"],
            "current_model": "o3-mini",
            "error": str(e)
        }


@router.get("/test-connection")
async def test_openai_connection():
    """🔗 Тест подключения к OpenAI API"""
    try:
        from app.services.openai_service import OpenAIService

        openai_service = OpenAIService()
        result = await openai_service.test_connection()

        return result

    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
        return {
            "status": "error",
            "model": "o3-mini",
            "error": str(e)
        }


# 🎯 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ

async def _send_to_telegram_bg(analysis_result: dict, analysis_type: str):
    """Background task для отправки в Telegram"""
    try:
        from app.services.telegram_service import TelegramService
        telegram = TelegramService()
        await telegram.send_ai_analysis_report(analysis_result, urgent_mode=False)
        logger.info(f"✅ Background task: {analysis_type} отправлен в Telegram")
    except Exception as e:
        logger.error(f"❌ Background task error for {analysis_type}: {e}")


# 📖 ИНФОРМАЦИОННЫЕ ENDPOINTS

@router.get("/help")
async def get_analysis_help():
    """📖 Справка по новым возможностям анализа"""
    return {
        "message": "AI анализ оптимизирован для работы с полной базой данных",
        "new_features": {
            "scheduled_analysis": {
                "description": "Автоматический анализ 2 раза в день (09:00 и 18:00)",
                "endpoint": "/analysis/scheduled-analysis",
                "benefits": ["Регулярный поиск лучших сделок", "Анализ описаний", "HTML отчеты"]
            },
            "full_market_analysis": {
                "endpoint": "/analysis/full-market",
                "description": "Анализ всего рынка одним запросом (экономия токенов)",
                "benefits": ["Полная картина рынка", "Меньше затрат на API", "Comprehensive insights"]
            },
            "market_trends": {
                "endpoint": "/analysis/market-trends",
                "description": "Анализ трендов на основе всей базы данных",
                "benefits": ["Динамика рынка", "Прогнозы", "Seasonal patterns"]
            },
            "database_statistics": {
                "endpoint": "/analysis/database-stats",
                "description": "Детальная статистика без AI (быстро и бесплатно)",
                "benefits": ["Мгновенные данные", "Без токенов", "Real-time insights"]
            }
        },
        "scheduled_analysis": {
            "frequency": "2 раза в день",
            "schedule": "09:00 и 18:00 (Кипрское время)",
            "focus": "Поиск лучших предложений с анализом описаний",
            "outputs": ["HTML отчет", "Топ предложения дня", "Telegram уведомления"]
        },
        "migration_guide": {
            "old_way": "Анализ каждого фильтра отдельно (/analysis/by-filter)",
            "new_way": "Анализ всей базы сразу (/analysis/full-market)",
            "scheduled_way": "Автоматический поиск сделок (/analysis/scheduled-analysis)",
            "token_savings": "До 80% экономии токенов OpenAI",
            "better_insights": "Более полная картина рынка и трендов"
        },
        "recommended_workflow": [
            "1. Проверьте статистику: GET /analysis/database-stats",
            "2. Если машин >= 20: POST /analysis/full-market",
            "3. Для трендов: POST /analysis/market-trends",
            "4. Для поиска сделок: POST /analysis/scheduled-analysis",
            "5. Проверьте расписание: GET /analysis/scheduler-status",
            "6. Legacy фильтры: POST /analysis/by-filter/{filter_name}"
        ]
    }