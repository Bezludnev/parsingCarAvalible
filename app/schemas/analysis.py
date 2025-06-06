# app/schemas/analysis.py - ОБНОВЛЕННАЯ с поддержкой описаний
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class CarSummary(BaseModel):
    id: int
    title: str
    brand: str
    year: Optional[int]
    price: str
    link: str
    mileage: Optional[int] = None
    description: Optional[str] = None  # НОВОЕ ПОЛЕ для описаний


class AnalysisRequest(BaseModel):
    filter_name: Optional[str] = None
    car_ids: Optional[List[int]] = None
    brand: Optional[str] = None
    limit: int = 20


class ComparisonRequest(BaseModel):
    car_ids: List[int]


class RecentCarsRequest(BaseModel):
    days: int = 7
    limit: int = 30


class FullMarketAnalysisRequest(BaseModel):
    """Запрос для полного анализа рынка"""
    min_cars_per_brand: int = 5
    include_descriptions: bool = True  # Включать ли описания в анализ


class MarketTrendsRequest(BaseModel):
    """Запрос для анализа трендов рынка"""
    days: int = 14
    include_recent_descriptions: bool = True


class AnalysisResponse(BaseModel):
    total_cars_analyzed: int
    analysis_type: str
    cars_data: List[CarSummary]

    # Поля для полного анализа рынка
    market_overview: Optional[str] = None
    brand_analysis: Optional[str] = None

    # Поля для анализа трендов
    market_dynamics: Optional[str] = None
    price_trends: Optional[str] = None
    forecast: Optional[str] = None

    # Legacy поля (для обратной совместимости)
    top_recommendations: Optional[str] = None
    detailed_analysis: Optional[str] = None
    general_conclusions: Optional[str] = None
    full_analysis: Optional[str] = None

    # Опциональные поля в зависимости от типа анализа
    filter_name: Optional[str] = None
    brand: Optional[str] = None
    days_period: Optional[int] = None
    trends_period_days: Optional[int] = None
    compared_car_ids: Optional[List[int]] = None
    recommended_car_ids: Optional[List[int]] = None
    brands_analyzed: Optional[List[str]] = None
    brands_statistics: Optional[Dict[str, int]] = None

    # Метаданные
    model_used: Optional[str] = "o3-mini"
    api_version: Optional[str] = "responses_v1"
    analysis_timestamp: Optional[str] = None
    database_snapshot: Optional[bool] = False
    descriptions_included: Optional[bool] = True  # НОВОЕ: указывает включены ли описания

    # Статус
    success: Optional[bool] = True
    error: Optional[str] = None


class QuickAnalysisResponse(BaseModel):
    """Краткий анализ для быстрого просмотра"""
    success: bool
    filter_name: str
    total_cars: int
    quick_recommendation: str
    recommended_link: Optional[str] = None
    analysis_type: str
    error: Optional[str] = None


class DatabaseStatsResponse(BaseModel):
    """Статистика по базе данных"""
    status: str
    global_statistics: Dict[str, Any]
    recent_week_statistics: Dict[str, Any]
    brands_breakdown: Dict[str, int]
    filters_breakdown: Dict[str, int]
    price_ranges_analysis: Dict[str, int]
    year_distribution: Dict[int, int]
    daily_activity_last_30_days: Dict[str, int]
    analysis_ready: bool
    recommended_analysis: str


class MarketSummaryResponse(BaseModel):
    """Быстрая сводка по рынку"""
    success: bool
    analysis_type: str
    total_cars_in_db: int
    avg_price: Optional[float]
    avg_year: Optional[float]
    avg_mileage: Optional[float]
    recent_week_additions: int
    brands_breakdown: Dict[str, int]
    most_popular_brand: Optional[str]
    analysis_timestamp: str


class AnalysisStatusResponse(BaseModel):
    """Статус системы анализа"""
    status: str
    ai_service: str
    model: str
    database_cars: int
    analysis_ready: bool
    recommended_endpoint: str
    features: List[str]
    connection_test: str
    error: Optional[str] = None