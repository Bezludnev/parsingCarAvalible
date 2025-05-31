# app/api/reports.py - API для управления HTML отчетами
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from app.services.html_service import HTMLReportService
from app.services.telegram_service import TelegramService
from typing import List, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["HTML Reports"])


@router.get("/list")
async def get_reports_list(limit: int = Query(default=10, ge=1, le=50)):
    """📋 Получить список HTML отчетов"""
    try:
        html_service = HTMLReportService()
        reports = html_service.get_reports_list(limit)

        return {
            "status": "success",
            "total_reports": len(reports),
            "reports": reports
        }

    except Exception as e:
        logger.error(f"Ошибка получения списка отчетов: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.get("/download/{filename}")
async def download_report(filename: str):
    """📥 Скачать HTML отчет по имени файла"""
    try:
        html_service = HTMLReportService()
        file_path = html_service.reports_dir / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Отчет не найден")

        if not filename.endswith('.html'):
            raise HTTPException(status_code=400, detail="Неверный формат файла")

        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type='text/html'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка скачивания отчета {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.delete("/cleanup")
async def cleanup_old_reports(keep_days: int = Query(default=7, ge=1, le=30)):
    """🗑️ Удалить старые HTML отчеты"""
    try:
        html_service = HTMLReportService()
        deleted_count = html_service.clean_old_reports(keep_days)

        return {
            "status": "success",
            "message": f"Удалено {deleted_count} отчетов старше {keep_days} дней",
            "deleted_count": deleted_count,
            "keep_days": keep_days
        }

    except Exception as e:
        logger.error(f"Ошибка очистки отчетов: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.post("/send-list-to-telegram")
async def send_reports_list_to_telegram():
    """📱 Отправить список отчетов в Telegram"""
    try:
        telegram_service = TelegramService()
        await telegram_service.send_reports_list()

        return {
            "status": "success",
            "message": "Список отчетов отправлен в Telegram"
        }

    except Exception as e:
        logger.error(f"Ошибка отправки списка в Telegram: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.get("/stats")
async def get_reports_statistics():
    """📊 Статистика по HTML отчетам"""
    try:
        html_service = HTMLReportService()
        reports = html_service.get_reports_list(100)  # Получаем больше для статистики

        if not reports:
            return {
                "status": "success",
                "total_reports": 0,
                "total_size_mb": 0,
                "avg_size_mb": 0,
                "oldest_report": None,
                "newest_report": None
            }

        total_size_mb = sum(report["size_mb"] for report in reports)
        avg_size_mb = round(total_size_mb / len(reports), 2)

        # Сортируем по дате создания
        reports_by_date = sorted(reports, key=lambda x: x["created"])
        oldest = reports_by_date[0] if reports_by_date else None
        newest = reports_by_date[-1] if reports_by_date else None

        return {
            "status": "success",
            "total_reports": len(reports),
            "total_size_mb": round(total_size_mb, 2),
            "avg_size_mb": avg_size_mb,
            "oldest_report": oldest,
            "newest_report": newest
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики отчетов: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@router.post("/test-html-generation")
async def test_html_generation():
    """🧪 Тест создания HTML отчета (с тестовыми данными)"""
    try:
        # Создаем тестовые данные для отчета
        test_analysis_result = {
            "total_cars_analyzed": 3,
            "analysis_type": "test",
            "filter_name": "test_filter",
            "model_used": "test_model",
            "top_recommendations": """
1. Автомобиль #1 - отличное соотношение цена/качество
2. Автомобиль #2 - надежная модель с низким пробегом
3. Автомобиль #3 - премиум класс по доступной цене
            """.strip(),
            "detailed_analysis": """
Автомобиль #1:
✅ Плюсы: Низкий пробег, хорошее техническое состояние
❌ Минусы: Старая модель
💰 Справедливость цены: Соответствует рынку
📊 Рекомендация: ПОКУПАТЬ

Автомобиль #2:
✅ Плюсы: Премиум марка, полная комплектация
❌ Минусы: Высокий пробег
💰 Справедливость цены: Переплата 10%
📊 Рекомендация: ТОРГОВАТЬСЯ
            """.strip(),
            "general_conclusions": """
На рынке представлены разнообразные варианты в данной ценовой категории.
Рекомендуется обратить внимание на автомобили с пробегом до 150,000 км.
Лучшее соотношение цена/качество показывают модели 2015-2018 годов.
            """.strip(),
            "recommended_car_ids": [1, 3],
            "cars_data": [
                {
                    "id": 1,
                    "title": "BMW 3 Series 320d 2016",
                    "brand": "BMW",
                    "year": 2016,
                    "price": "€15,000",
                    "mileage": 120000,
                    "link": "https://example.com/car1"
                },
                {
                    "id": 2,
                    "title": "Mercedes C-Class 2017",
                    "brand": "Mercedes",
                    "year": 2017,
                    "price": "€18,500",
                    "mileage": 95000,
                    "link": "https://example.com/car2"
                },
                {
                    "id": 3,
                    "title": "Audi A4 2015",
                    "brand": "Audi",
                    "year": 2015,
                    "price": "€13,200",
                    "mileage": 140000,
                    "link": "https://example.com/car3"
                }
            ]
        }

        html_service = HTMLReportService()
        file_path = html_service.generate_analysis_report(test_analysis_result)
        filename = os.path.basename(file_path)

        return {
            "status": "success",
            "message": "Тестовый HTML отчет создан успешно",
            "filename": filename,
            "file_path": file_path,
            "download_url": f"/reports/download/{filename}"
        }

    except Exception as e:
        logger.error(f"Ошибка создания тестового отчета: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")