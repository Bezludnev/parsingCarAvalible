# app/services/negotiation_service.py
from app.models.car import Car
from app.services.openai_service import OpenAIService
from typing import Dict, List
import re


class NegotiationService:
    def __init__(self):
        self.ai = OpenAIService()

    def calculate_offer_strategy(self, car: Car, budget: int) -> Dict:
        """Calculates smart offer based on car condition & market"""
        asking_price = self._extract_price_number(car.price)
        if not asking_price:
            return {"error": "Cannot parse asking price"}

        # Basic negotiation math
        offer_percentage = budget / asking_price if asking_price > 0 else 0

        # Urgency signals boost negotiation power
        urgency_score = self._calculate_urgency_score(car)

        strategy = {
            "asking_price": asking_price,
            "your_budget": budget,
            "offer_percentage": round(offer_percentage * 100, 1),
            "urgency_score": urgency_score,
            "negotiation_power": "HIGH" if urgency_score > 3 else "MEDIUM",
            "recommended_approach": self._get_approach(offer_percentage, urgency_score)
        }

        return strategy

    def generate_offer_message(self, car: Car, offer_amount: int, language: str = "en") -> str:
        """Generates personalized offer message"""
        urgency_score = self._calculate_urgency_score(car)

        templates = {
            "en_direct": """Hi! I'm interested in your {brand} {year}.
I can offer €{offer} cash, immediate purchase.
Is this acceptable? Can arrange viewing today.
Thanks!""",

            "en_negotiation": """Hi! Your {brand} {year} looks perfect for me.
My budget is €{offer} cash - I know you're asking €{asking}, 
but would you consider my offer? No financing delays, quick deal.
What do you think?""",

            "ru_direct": """Привет! Интересует ваш {brand} {year}.
Предлагаю €{offer} наличными, сразу покупка.
Подходит? Можно посмотреть сегодня.
Спасибо!""",

            "ru_negotiation": """Привет! Ваш {brand} {year} как раз то что нужно.
Бюджет €{offer} наличными - знаю что просите €{asking},
но рассмотрите мое предложение? Без кредитов, быстрая сделка.
Как считаете?"""
        }

        asking_price = self._extract_price_number(car.price) or "unknown"
        offer_percentage = (offer_amount / asking_price * 100) if isinstance(asking_price, int) else 0

        # Choose template based on offer strength
        if offer_percentage >= 90:
            template_key = f"{language}_direct"
        else:
            template_key = f"{language}_negotiation"

        template = templates.get(template_key, templates["en_direct"])

        return template.format(
            brand=car.brand or "car",
            year=car.year or "",
            offer=f"{offer_amount:,}",
            asking=f"{asking_price:,}" if isinstance(asking_price, int) else asking_price
        )

    def _calculate_urgency_score(self, car: Car) -> int:
        """Calculates urgency score 0-5 based on description & price changes"""
        score = 0
        text = (car.description or "") + " " + (car.title or "")
        text_lower = text.lower()

        # Urgent keywords
        urgent_keywords = [
            ("срочно", 2), ("urgent", 2), ("must sell", 2),
            ("переезд", 2), ("emigrating", 2), ("leaving", 2),
            ("need money", 1), ("negotiable", 1), ("reduced", 1),
            ("price drop", 1), ("торг", 1), ("обмен", 1)
        ]

        for keyword, points in urgent_keywords:
            if keyword in text_lower:
                score += points

        # Recent price drops
        if car.price_changes_count and car.price_changes_count > 0:
            score += 1

        # Long listing (older posts = more desperate)
        if car.date_posted and "month" in car.date_posted.lower():
            score += 1

        return min(score, 5)  # Cap at 5

    def _extract_price_number(self, price_text: str) -> int:
        """Extracts numeric price from text"""
        if not price_text:
            return None

        numbers = re.findall(r'\d+', price_text.replace(',', '').replace(' ', ''))
        if numbers:
            return int(''.join(numbers))
        return None

    def _get_approach(self, offer_percentage: float, urgency_score: int) -> str:
        """Recommends negotiation approach"""
        if offer_percentage >= 0.95:
            return "DIRECT - offer very close to asking price"
        elif offer_percentage >= 0.85:
            return "CONFIDENT - reasonable offer, mention cash benefits"
        elif urgency_score >= 3:
            return "AGGRESSIVE - seller seems motivated, push harder"
        elif offer_percentage >= 0.75:
            return "DIPLOMATIC - significant gap, need good reasoning"
        else:
            return "LONG SHOT - major gap, focus on quick cash sale"


# app/api/negotiation.py
from fastapi import APIRouter, HTTPException
from app.services.negotiation_service import NegotiationService
from app.repository.car_repository import CarRepository
from app.database import async_session

router = APIRouter(prefix="/negotiation", tags=["Smart Negotiation"])


@router.post("/generate-offer/{car_id}")
async def generate_offer_message(
        car_id: int,
        offer_amount: int,
        language: str = "en"  # en/ru
):
    """🤝 Generate smart offer message for seller"""
    async with async_session() as session:
        repo = CarRepository(session)
        car = await repo.get_cars_by_ids([car_id])

        if not car:
            raise HTTPException(404, "Car not found")

        service = NegotiationService()
        strategy = service.calculate_offer_strategy(car[0], offer_amount)
        message = service.generate_offer_message(car[0], offer_amount, language)

        return {
            "car": {
                "id": car_id,
                "title": car[0].title,
                "asking_price": car[0].price
            },
            "strategy": strategy,
            "message": message,
            "tips": [
                "📱 Copy message and send via Bazaraki chat",
                "💰 Emphasize cash payment advantage",
                "⏰ Mention quick viewing/purchase timeline",
                "🤝 Be polite but confident"
            ]
        }


@router.get("/market-position/{car_id}")
async def analyze_market_position(car_id: int, your_budget: int):
    """📊 Analyze your negotiation position"""
    async with async_session() as session:
        repo = CarRepository(session)
        car = await repo.get_cars_by_ids([car_id])

        if not car:
            raise HTTPException(404, "Car not found")

        service = NegotiationService()
        analysis = service.calculate_offer_strategy(car[0], your_budget)

        return {
            "position_analysis": analysis,
            "negotiation_tips": {
                "strengths": [
                    "💵 Cash payment (no financing delays)",
                    "⚡ Quick decision making",
                    "📋 Serious buyer with budget ready"
                ],
                "leverage_points": [
                    "🏦 No bank approval needed",
                    "📅 Flexible viewing schedule",
                    "🔄 Can complete purchase this week"
                ]
            }
        }