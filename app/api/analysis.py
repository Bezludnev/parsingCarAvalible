# app/api/analysis.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.services.analysis_service import AnalysisService
from app.schemas.analysis import (
    AnalysisResponse,
    ComparisonRequest,
    RecentCarsRequest,
    QuickAnalysisResponse
)
from typing import List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/by-filter/{filter_name}", response_model=AnalysisResponse)
async def analyze_by_filter(
        filter_name: str,
        limit: int = 20
):
    """Анализирует машины по фильтру (mercedes, bmw, audi)"""
    try:
        service = AnalysisService()
        result = await service.analyze_cars_by_filter(filter_name, limit)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")


@router.post("/compare", response_model=AnalysisResponse)
async def compare_cars(request: ComparisonRequest):
    """Сравнивает конкретные машины по ID"""
    try:
        service = AnalysisService()
        result = await service.compare_specific_cars(request.car_ids)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result
    except Exception as e:
        logger.error(f"Comparison error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сравнения: {str(e)}")


@router.post("/recent", response_model=AnalysisResponse)
async def analyze_recent_cars(request: RecentCarsRequest):
    """Анализирует недавние машины"""
    try:
        service = AnalysisService()
        result = await service.analyze_all_recent_cars(request.days, request.limit)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result
    except Exception as e:
        logger.error(f"Recent analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")


@router.get("/brand/{brand}", response_model=AnalysisResponse)
async def analyze_by_brand(
        brand: str,
        limit: int = 15
):
    """Анализ по марке"""
    try:
        service = AnalysisService()
        result = await service.get_brand_analysis(brand, limit)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result
    except Exception as e:
        logger.error(f"Brand analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка анализа марки: {str(e)}")


@router.get("/quick/{filter_name}")
async def quick_analysis(filter_name: str):
    """Быстрый анализ без детальной обработки"""
    try:
        service = AnalysisService()

        # Получаем краткий анализ
        result = await service.analyze_cars_by_filter(filter_name, 10)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        # Извлекаем ключевые моменты
        recommendations = result.get("top_recommendations", "").split("\n")[:3]

        return {
            "total_cars": result["total_cars_analyzed"],
            "top_3_recommendations": [rec.strip() for rec in recommendations if rec.strip()],
            "analysis_summary": result.get("general_conclusions", "")[:300] + "...",
            "filter_name": filter_name
        }
    except Exception as e:
        logger.error(f"Quick analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка быстрого анализа: {str(e)}")


@router.post("/background/{filter_name}")
async def start_background_analysis(
        filter_name: str,
        background_tasks: BackgroundTasks,
        limit: int = 30
):
    """Запускает анализ в фоне для больших объемов"""

    async def run_analysis():
        try:
            service = AnalysisService()
            result = await service.analyze_cars_by_filter(filter_name, limit)
            logger.info(f"Background analysis completed for {filter_name}")
            # Здесь можно отправить результат в Telegram или сохранить в кеш
        except Exception as e:
            logger.error(f"Background analysis failed: {e}")

    background_tasks.add_task(run_analysis)

    return {
        "message": f"Анализ {filter_name} запущен в фоне",
        "filter_name": filter_name,
        "limit": limit
    }