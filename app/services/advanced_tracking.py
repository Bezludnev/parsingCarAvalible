# app/services/advanced_tracking_service.py
from app.models.car import Car
from app.services.telegram_service import TelegramService
from app.repository.car_repository import CarRepository
from datetime import datetime, timedelta
import logging

class AdvancedTrackingService:
    def __init__(self):
        self.telegram = TelegramService()
    
    async def detect_seller_desperation_signals(self, car: Car) -> Dict:
        """🎯 Detects if seller is getting desperate"""
        signals = {
            "desperation_score": 0,
            "signals_found": [],
            "recommended_action": "WAIT"
        }
        
        # Multiple price drops = desperation
        if car.price_changes_count and car.price_changes_count >= 2:
            signals["desperation_score"] += 3
            signals["signals_found"].append("Multiple price drops")
        
        # Recent price drop
        if car.price_changed_at and car.price_changed_at > datetime.now() - timedelta(days=7):
            signals["desperation_score"] += 2
            signals["signals_found"].append("Recent price reduction")
            
        # Long-term listing (estimate from description age indicators)
        description = car.description or ""
        if any(word in description.lower() for word in ["months", "long time", "still available"]):
            signals["desperation_score"] += 2
            signals["signals_found"].append("Long-term listing")
            
        # Urgent keywords in recent updates
        if car.description_changed_at and car.description_changed_at > datetime.now() - timedelta(days=3):
            urgent_words = ["срочно", "urgent", "must sell", "need gone", "emigrating"]
            if any(word in description.lower() for word in urgent_words):
                signals["desperation_score"] += 3
                signals["signals_found"].append("Added urgent keywords recently")
        
        # Recommendation based on score
        if signals["desperation_score"] >= 5:
            signals["recommended_action"] = "MAKE_AGGRESSIVE_OFFER"
        elif signals["desperation_score"] >= 3:
            signals["recommended_action"] = "MAKE_REASONABLE_OFFER"
        elif signals["desperation_score"] >= 1:
            signals["recommended_action"] = "MONITOR_CLOSELY"
            
        return signals
    
    async def track_market_competition(self, car: Car) -> Dict:
        """📊 Tracks similar cars to understand competition"""
        async with async_session() as session:
            repo = CarRepository(session)
            
            # Find similar cars (same brand, similar year/mileage)
            similar_cars = await repo.get_similar_cars(
                brand=car.brand,
                year_range=(car.year - 2, car.year + 2),
                price_range=self._calculate_price_range(car.price)
            )
            
            competition_analysis = {
                "similar_cars_count": len(similar_cars),
                "market_position": "UNKNOWN",
                "price_competitiveness": "UNKNOWN",
                "recommendations": []
            }
            
            if len(similar_cars) > 1:
                prices = [self._extract_price_number(c.price) for c in similar_cars if self._extract_price_number(c.price)]
                if prices:
                    avg_price = sum(prices) / len(prices)
                    car_price = self._extract_price_number(car.price)
                    
                    if car_price and car_price < avg_price * 0.9:
                        competition_analysis["price_competitiveness"] = "VERY_GOOD"
                        competition_analysis["recommendations"].append("Price below market - act fast!")
                    elif car_price and car_price < avg_price * 1.1:
                        competition_analysis["price_competitiveness"] = "COMPETITIVE"
                        competition_analysis["recommendations"].append("Fair market price")
                    else:
                        competition_analysis["price_competitiveness"] = "EXPENSIVE"
                        competition_analysis["recommendations"].append("Overpriced - good for negotiation")
            
            return competition_analysis
    
    async def auto_offer_suggestions(self, budget: int, max_mileage: int = 150000) -> List[Dict]:
        """💡 Automatically suggests cars to make offers on"""
        async with async_session() as session:
            repo = CarRepository(session)
            
            # Get cars with recent price drops or urgency signals
            candidates = await repo.get_negotiation_candidates(
                max_price=budget * 1.2,  # Include cars slightly over budget
                max_mileage=max_mileage,
                has_price_drops=True
            )
            
            suggestions = []
            for car in candidates:
                desperation = await self.detect_seller_desperation_signals(car)
                competition = await self.track_market_competition(car)
                
                if desperation["desperation_score"] >= 2:  # Some desperation signals
                    offer_amount = min(budget, int(self._extract_price_number(car.price) * 0.85))
                    
                    suggestions.append({
                        "car": {
                            "id": car.id,
                            "title": car.title,
                            "price": car.price,
                            "link": car.link
                        },
                        "suggested_offer": offer_amount,
                        "success_probability": self._calculate_success_probability(desperation, competition),
                        "reasoning": f"Desperation score: {desperation['desperation_score']}/5. " + 
                                   " ".join(desperation["signals_found"])
                    })
            
            # Sort by success probability
            suggestions.sort(key=lambda x: x["success_probability"], reverse=True)
            return suggestions[:10]  # Top 10 suggestions
    
    def _calculate_price_range(self, price_str: str) -> tuple:
        """Helper to calculate price range for similar cars"""
        price = self._extract_price_number(price_str)
        if price:
            return (price * 0.8, price * 1.2)
        return (0, 999999)
    
    def _extract_price_number(self, price_text: str) -> int:
        """Extract number from price text"""
        if not price_text:
            return None
        import re
        numbers = re.findall(r'\d+', price_text.replace(',', ''))
        return int(''.join(numbers)) if numbers else None
    
    def _calculate_success_probability(self, desperation: Dict, competition: Dict) -> float:
        """Calculate probability of successful negotiation"""
        base_probability = 0.3  # 30% base chance
        
        # Desperation signals boost probability
        base_probability += (desperation["desperation_score"] / 5) * 0.4
        
        # Price competitiveness affects probability
        if competition["price_competitiveness"] == "EXPENSIVE":
            base_probability += 0.2
        elif competition["price_competitiveness"] == "VERY_GOOD":
            base_probability -= 0.1  # Seller knows they have good price
            
        return min(0.9, max(0.1, base_probability))

# app/api/tracking.py - New endpoints
@router.post("/track-desperation/{car_id}")
async def analyze_seller_desperation(car_id: int):
    """🎯 Analyze seller desperation signals"""
    service = AdvancedTrackingService()
    # ... get car from DB
    analysis = await service.detect_seller_desperation_signals(car)
    return analysis

@router.get("/offer-suggestions")
async def get_auto_offer_suggestions(
    budget: int = 12000,
    max_mileage: int = 150000
):
    """💡 Get automated offer suggestions based on market analysis"""
    service = AdvancedTrackingService()
    suggestions = await service.auto_offer_suggestions(budget, max_mileage)
    return {
        "your_budget": budget,
        "suggestions_count": len(suggestions),
        "top_suggestions": suggestions
    }

# NEW: Add to CarRepository
async def get_similar_cars(self, brand: str, year_range: tuple, price_range: tuple) -> List[Car]:
    """Find similar cars for competition analysis"""
    result = await self.session.execute(
        select(Car).where(
            and_(
                Car.brand.ilike(f"%{brand}%"),
                Car.year.between(year_range[0], year_range[1]),
                # Add price filtering logic here
            )
        ).limit(20)
    )
    return result.scalars().all()

async def get_negotiation_candidates(self, max_price: int, max_mileage: int, has_price_drops: bool = False) -> List[Car]:
    """Get cars that are good candidates for negotiation"""
    query = select(Car).where(
        and_(
            Car.mileage <= max_mileage,
            # Add price filtering
            Car.is_notified == True  # Only processed cars
        )
    )
    
    if has_price_drops:
        query = query.where(Car.price_changes_count > 0)
        
    result = await self.session.execute(query.limit(50))
    return result.scalars().all()