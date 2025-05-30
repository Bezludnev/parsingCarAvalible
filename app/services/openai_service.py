# app/services/openai_service.py - ВЕРСИЯ ДЛЯ o3-mini
from openai import AsyncOpenAI
from typing import List, Dict, Any
from app.config import settings
from app.models.car import Car
import logging
import asyncio

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def analyze_cars(self, cars: List[Car]) -> Dict[str, Any]:
        """Основной метод анализа машин через o3-mini"""

        if not cars:
            return {"error": "Нет машин для анализа", "total_cars_analyzed": 0}

        cars_data = self._prepare_cars_data(cars)
        prompt = self._build_analysis_prompt(cars_data)

        try:
            # ИСПОЛЬЗУЕМ o3-mini
            response = await self.client.chat.completions.create(
                model="o3-mini",
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=3000,  # o3-mini может обрабатывать больше токенов
                temperature=0.3
            )

            analysis_text = response.choices[0].message.content
            return self._parse_analysis_response(analysis_text, cars)

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise Exception(f"Ошибка AI анализа: {str(e)}")

    def _get_system_prompt(self) -> str:
        return """Ты опытный автоэксперт с 20-летним стажем на европейском рынке подержанных автомобилей.

ТВОЯ ЭКСПЕРТИЗА:
- Знание типичных проблем каждой модели BMW, Mercedes, Audi, Volkswagen
- Понимание реальной стоимости обслуживания в Европе
- Оценка соотношения цена/качество на рынке Кипра
- Прогноз износа по пробегу и году выпуска
- Особенности климата Кипра (жара, соль) и их влияние на автомобили

ПРИНЦИПЫ АНАЛИЗА:
- Честно указывай на известные проблемы моделей
- Учитывай климат Кипра (высокие температуры, морская соль)
- Помни про дорогие запчасти премиум-брендов
- Оценивай реальную рыночную стоимость
- Предупреждай о скрытых расходах на обслуживание

СТИЛЬ ОТВЕТА: практичный, конкретный, без лишних слов. Давай четкие рекомендации."""

    def _prepare_cars_data(self, cars: List[Car]) -> str:
        """Подготавливает данные машин для анализа"""
        cars_info = []

        for i, car in enumerate(cars, 1):
            # Очищаем цену от символов
            price_clean = car.price.replace('€', '').replace(',', '').replace(' ',
                                                                              '').strip() if car.price else 'не указана'

            # Извлекаем числовое значение цены
            price_numeric = ""
            if price_clean.isdigit():
                price_numeric = f" ({int(price_clean):,} евро)"

            info = f"""
Автомобиль #{i}:
• Модель: {car.title}
• Марка: {car.brand}
• Год выпуска: {car.year or 'не указан'}
• Пробег: {f"{car.mileage:,} км" if car.mileage else 'не указан'}
• Цена: {car.price}{price_numeric}
• Характеристики: {car.features[:250] if car.features else 'нет данных'}
• Местоположение: {car.place}
• ID для ссылки: {car.id}
"""
            cars_info.append(info)

        return "\n".join(cars_info)

    def _build_analysis_prompt(self, cars_data: str) -> str:
        return f"""
Проанализируй эти автомобили для покупки на Кипре. Учти особенности местного климата и рынка:

{cars_data}

ПРОВЕДИ АНАЛИЗ ПО КРИТЕРИЯМ:
1. Надежность модели и типичные проблемы
2. Соответствие цены местному рынку
3. Состояние по пробегу/году (учти климат Кипра)
4. Стоимость обслуживания и доступность запчастей
5. Перспективы сохранения стоимости

СТРУКТУРА ОТВЕТА:
**ТОП-3 РЕКОМЕНДАЦИИ:**
1. Автомобиль #X - краткая причина (цена/качество/надежность)
2. Автомобиль #Y - краткая причина
3. Автомобиль #Z - краткая причина

**ДЕТАЛЬНЫЙ АНАЛИЗ:**
Для каждого автомобиля:
- ✅ Плюсы и преимущества
- ❌ Минусы и возможные проблемы
- 💰 Справедливость цены (переплата/недоплата)
- 🔧 Ожидаемые расходы на обслуживание
- 📊 Рекомендация: ПОКУПАТЬ/НЕ ПОКУПАТЬ/ТОРГОВАТЬСЯ

**ОБЩИЕ ВЫВОДЫ:**
Итоговые рекомендации по выбору в данной категории автомобилей.
"""

    def _parse_analysis_response(self, analysis_text: str, cars: List[Car]) -> Dict[str, Any]:
        """Структурирует ответ от o3-mini"""
        sections = analysis_text.split("**")

        top_recommendations = ""
        detailed_analysis = ""
        general_conclusions = ""

        for i, section in enumerate(sections):
            if "ТОП-3" in section or "TOP-3" in section:
                top_recommendations = sections[i + 1] if i + 1 < len(sections) else ""
            elif "ДЕТАЛЬНЫЙ" in section or "DETAILED" in section:
                detailed_analysis = sections[i + 1] if i + 1 < len(sections) else ""
            elif "ОБЩИЕ" in section or "ВЫВОДЫ" in section:
                general_conclusions = sections[i + 1] if i + 1 < len(sections) else ""

        # Извлекаем рекомендованные ID машин
        recommended_ids = self._extract_recommended_car_ids(top_recommendations, cars)

        return {
            "total_cars_analyzed": len(cars),
            "top_recommendations": top_recommendations.strip(),
            "detailed_analysis": detailed_analysis.strip(),
            "general_conclusions": general_conclusions.strip(),
            "full_analysis": analysis_text,
            "recommended_car_ids": recommended_ids,
            "model_used": "o3-mini",  # Указываем используемую модель
            "cars_data": [
                {
                    "id": car.id,
                    "title": car.title,
                    "brand": car.brand,
                    "year": car.year,
                    "price": car.price,
                    "mileage": car.mileage,
                    "link": car.link
                } for car in cars
            ]
        }

    def _extract_recommended_car_ids(self, recommendations: str, cars: List[Car]) -> List[int]:
        """Извлекает ID рекомендованных машин из текста"""
        import re

        # Ищем паттерны типа "Автомобиль #1", "Автомобиль #3"
        car_numbers = re.findall(r'Автомобиль #(\d+)', recommendations)

        recommended_ids = []
        for num_str in car_numbers:
            try:
                car_index = int(num_str) - 1  # Индекс в списке (начиная с 0)
                if 0 <= car_index < len(cars):
                    recommended_ids.append(cars[car_index].id)
            except (ValueError, IndexError):
                continue

        return recommended_ids

    async def get_quick_recommendation(self, cars: List[Car]) -> str:
        """Быстрая рекомендация для топ-1 машины через o3-mini"""
        if not cars:
            return "Нет машин для анализа"

        try:
            prompt = f"""
Из этих автомобилей выбери ОДНУ лучшую покупку для Кипра:

{self._prepare_cars_data(cars[:5])}

Учти: климат Кипра, доступность сервиса, соотношение цена/качество.
Ответь одним предложением: "Рекомендую Автомобиль #X потому что [конкретная причина]"
"""

            # ИСПОЛЬЗУЕМ o3-mini для быстрых рекомендаций
            response = await self.client.chat.completions.create(
                model="o3-mini",
                messages=[
                    {"role": "system", "content": "Ты автоэксперт на Кипре. Давай краткие практичные рекомендации."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.2
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Quick recommendation error: {e}")
            return "Быстрый анализ недоступен"

    async def test_connection(self) -> Dict[str, Any]:
        """Тест подключения к OpenAI API с o3-mini"""
        try:
            response = await self.client.chat.completions.create(
                model="o3-mini",
                messages=[{"role": "user", "content": "Тест подключения"}],
                max_tokens=10
            )

            return {
                "status": "success",
                "model": "o3-mini",
                "response": response.choices[0].message.content
            }
        except Exception as e:
            logger.error(f"o3-mini connection test failed: {e}")
            return {
                "status": "error",
                "model": "o3-mini",
                "error": str(e)
            }

    async def get_available_models(self) -> List[str]:
        """Получает список доступных моделей"""
        try:
            models = await self.client.models.list()
            available = [model.id for model in models.data if 'gpt' in model.id or 'o3' in model.id]
            return sorted(available)
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            return ["o3-mini"]  # Fallback