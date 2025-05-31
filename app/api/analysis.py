# app/api/analysis.py - ОБНОВЛЕННАЯ ВЕРСИЯ с o3-mini
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from app.services.analysis_service import AnalysisService
from app.schemas.analysis import (
    AnalysisResponse,
    ComparisonRequest,
    RecentCarsRequest,
    QuickAnalysisResponse
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["AI Analysis"])


@router.post("/by-filter/{filter_name}", response_model=AnalysisResponse)
async def analyze_by_filter(
        filter_name: str,
        limit: int = Query(default=20, ge=5, le=50)
):
    """🤖 AI анализ машин по фильтру через o3-mini (mercedes, bmw, audi)"""
    try:
        service = AnalysisService()
        result = await service.analyze_cars_by_filter(filter_name, limit)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis error for filter {filter_name}: {e}")
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
        logger.error(f"Comparison error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сравнения: {str(e)}")


@router.post("/recent", response_model=AnalysisResponse)
async def analyze_recent_cars(request: RecentCarsRequest):
    """📅 Анализ недавних поступлений через o3-mini"""
    try:
        service = AnalysisService()
        result = await service.analyze_recent_cars(request.days, request.limit)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recent analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")


@router.get("/brand/{brand}", response_model=AnalysisResponse)
async def analyze_by_brand(
        brand: str,
        limit: int = Query(default=15, ge=5, le=30)
):
    """🏷️ Анализ по марке автомобиля через o3-mini"""
    try:
        service = AnalysisService()
        result = await service.get_brand_analysis(brand, limit)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Brand analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка анализа марки: {str(e)}")


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
        logger.error(f"Quick analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка быстрого анализа: {str(e)}")


@router.post("/send-to-telegram/{filter_name}")
async def send_analysis_to_telegram(filter_name: str, limit: int = Query(default=15, ge=5, le=30)):
    """📱 Отправить AI анализ в Telegram"""
    try:
        service = AnalysisService()
        result = await service.analyze_cars_by_filter(filter_name, limit)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        # Отправляем в Telegram
        from app.services.telegram_service import TelegramService
        telegram = TelegramService()
        await telegram.send_ai_analysis_report(result)

        return {
            "status": "sent_to_telegram",
            "filter_name": filter_name,
            "cars_analyzed": result["total_cars_analyzed"],
            "message": f"AI анализ {filter_name} отправлен в Telegram"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка отправки в Telegram: {str(e)}")


@router.post("/manual-analysis")
async def trigger_manual_analysis(filter_name: str = Query(default=None, description="Конкретный фильтр или все")):
    """🔧 Ручной запуск AI анализа с отправкой в Telegram"""
    try:
        from app.services.monitor_service import MonitorService

        monitor = MonitorService()
        result = await monitor.run_manual_ai_analysis(filter_name)

        return result

    except Exception as e:
        logger.error(f"Manual analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка ручного анализа: {str(e)}")


@router.get("/status")
async def get_analysis_status():
    """📊 Статус сервиса анализа с o3-mini"""
    try:
        from app.services.openai_service import OpenAIService

        openai_service = OpenAIService()
        connection_test = await openai_service.test_connection()

        if connection_test.get("status") == "success":
            return {
                "status": "operational",
                "ai_service": "online",
                "model": "o3-mini",
                "features": [
                    "filter_analysis",
                    "car_comparison",
                    "recent_analysis",
                    "brand_analysis",
                    "quick_insights"
                ],
                "supported_brands": ["mercedes", "bmw", "audi"],
                "connection_test": "passed"
            }
        else:
            return {
                "status": "degraded",
                "ai_service": "limited",
                "model": "o3-mini",
                "error": connection_test.get("error"),
                "connection_test": "failed"
            }

    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {
            "status": "offline",
            "ai_service": "offline",
            "model": "o3-mini",
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
            "total_models": len(models)
        }

    except Exception as e:
        logger.error(f"Models check failed: {e}")
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
        logger.error(f"Connection test failed: {e}")
        return {
            "status": "error",
            "model": "o3-mini",
            "error": str(e)
        }