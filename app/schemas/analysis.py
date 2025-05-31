# app/schemas/analysis.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class CarSummary(BaseModel):
    id: int
    title: str
    brand: str
    year: Optional[int]
    price: str
    link: str


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


class AnalysisResponse(BaseModel):
    total_cars_analyzed: int
    analysis_type: str
    top_recommendations: str
    detailed_analysis: str
    general_conclusions: str
    full_analysis: str
    cars_data: List[CarSummary]

    # Опциональные поля в зависимости от типа анализа
    filter_name: Optional[str] = None
    brand: Optional[str] = None
    days_period: Optional[int] = None
    compared_car_ids: Optional[List[int]] = None
    error: Optional[str] = None


class QuickAnalysisResponse(BaseModel):
    """Краткий анализ для быстрого просмотра"""
    total_cars: int
    top_3_recommendations: List[str]
    average_price_range: str
    best_value_car: Optional[CarSummary] = None
    analysis_summary: str