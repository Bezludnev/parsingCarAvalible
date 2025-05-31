# app/services/openai_service.py - ДЛЯ НОВОГО RESPONSES API
import httpx
from typing import List, Dict, Any
from app.config import settings
from app.models.car import Car
import logging
import asyncio

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.base_url = "https://api.openai.com/v1"

    async def analyze_cars(self, cars: List[Car]) -> Dict[str, Any]:
        """Основной метод анализа машин через новый Responses API"""

        if not cars:
            return {"error": "Нет машин для анализа", "total_cars_analyzed": 0}

        cars_data = self._prepare_cars_data(cars)
        input_text = self._build_analysis_input(cars_data)

        try:
            # НОВЫЙ RESPONSES API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/responses",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    json={
                        "model": "o3-mini",
                        "input": input_text
                    },
                    timeout=60.0
                )

                if response.status_code != 200:
                    raise Exception(f"API Error {response.status_code}: {response.text}")

                result = response.json()
                analysis_text = self._extract_response_text(result)

                return self._parse_analysis_response(analysis_text, cars)

        except Exception as e:
            logger.error(f"OpenAI Responses API error: {e}")
            raise Exception(f"Ошибка AI анализа: {str(e)}")

    def _extract_response_text(self, api_response: Dict) -> str:
        """Извлекает текст из нового формата ответа"""
        try:
            # Логируем структуру ответа для отладки
            logger.info(f"API Response structure: {list(api_response.keys())}")

            # ОСНОВНОЙ ПУТЬ: text на верхнем уровне
            if "text" in api_response:
                text_value = api_response["text"]
                logger.info(f"Found text at top level: {type(text_value)}")
                logger.info(
                    f"Text dict keys: {list(text_value.keys()) if isinstance(text_value, dict) else 'not dict'}")

                # Если text это dict, логируем его содержимое
                if isinstance(text_value, dict):
                    logger.info(f"Text dict content: {text_value}")
                    # Возможно format содержит данные
                    if "format" in text_value:
                        format_value = text_value["format"]
                        logger.info(f"Format content: {format_value}")
                else:
                    return str(text_value)

            # ПРОВЕРИМ OUTPUT детально - ВСЕ ЭЛЕМЕНТЫ!
            if "output" in api_response:
                output = api_response["output"]
                logger.info(
                    f"Output type: {type(output)}, length: {len(output) if isinstance(output, list) else 'not list'}")

                if isinstance(output, list):
                    # ПРОВЕРИМ ВСЕ ЭЛЕМЕНТЫ OUTPUT МАССИВА
                    for i, output_item in enumerate(output):
                        logger.info(f"Output[{i}] type: {type(output_item)}")

                        if isinstance(output_item, dict):
                            logger.info(f"Output[{i}] keys: {list(output_item.keys())}")
                            logger.info(f"Output[{i}] content: {output_item}")

                            # Проверим type элемента
                            item_type = output_item.get("type", "unknown")
                            logger.info(f"Output[{i}] type field: {item_type}")

                            # Если это message - скорее всего там наш анализ!
                            if item_type == "message":
                                logger.info(f"Found message type at output[{i}]!")

                                # Проверим content в message
                                if "content" in output_item:
                                    content_array = output_item["content"]
                                    logger.info(f"Message content type: {type(content_array)}")
                                    logger.info(f"Message content: {content_array}")

                                    if isinstance(content_array, list) and len(content_array) > 0:
                                        for j, content_item in enumerate(content_array):
                                            logger.info(f"Content[{j}]: {content_item}")
                                            if isinstance(content_item, dict) and "text" in content_item:
                                                analysis_text = content_item["text"]
                                                logger.info(f"FOUND ANALYSIS TEXT! Length: {len(str(analysis_text))}")
                                                return str(analysis_text)

                                # Проверим прямое текстовое поле
                                if "text" in output_item:
                                    return str(output_item["text"])

                            # Проверим summary в любом элементе
                            if "summary" in output_item:
                                summary = output_item["summary"]
                                logger.info(f"Output[{i}] summary type: {type(summary)}, content: {summary}")
                                if isinstance(summary, str) and len(summary) > 10:
                                    return summary

            # ПРОВЕРИМ REASONING поле (возможно там текст)
            if "reasoning" in api_response:
                reasoning = api_response["reasoning"]
                logger.info(f"Reasoning content: {reasoning}")
                if isinstance(reasoning, dict) and "summary" in reasoning:
                    return str(reasoning["summary"])

            # FALLBACK - ищем любую строку длиннее 50 символов
            def find_long_strings(obj, path=""):
                results = []
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        new_path = f"{path}.{key}" if path else key
                        if isinstance(value, str) and len(value) > 50:
                            results.append((new_path, value))
                        else:
                            results.extend(find_long_strings(value, new_path))
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        new_path = f"{path}[{i}]"
                        results.extend(find_long_strings(item, new_path))
                return results

            long_strings = find_long_strings(api_response)
            logger.info(f"Found long strings at: {[path for path, _ in long_strings]}")

            if long_strings:
                # Берем первую длинную строку
                path, text = long_strings[0]
                logger.info(f"Using text from {path}: {text[:100]}...")
                return text

            # ПОСЛЕДНИЙ FALLBACK
            logger.warning(f"No text found anywhere, converting full response")
            return str(api_response)

        except Exception as e:
            logger.error(f"Ошибка извлечения текста: {e}")
            return f"Ошибка обработки ответа: {str(e)}"

    def _get_system_context(self) -> str:
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

    def _build_analysis_input(self, cars_data: str) -> str:
        """Строит input для нового Responses API"""
        system_context = self._get_system_context()

        return f"""{system_context}

ЗАДАЧА: Проанализируй эти автомобили для покупки на Кипре. Учти особенности местного климата и рынка:

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
Итоговые рекомендации по выбору в данной категории автомобилей."""

    def _parse_analysis_response(self, analysis_text: str, cars: List[Car]) -> Dict[str, Any]:
        """Структурирует ответ от AI"""
        # Убеждаемся что это строка
        if not isinstance(analysis_text, str):
            logger.warning(f"analysis_text is not string: {type(analysis_text)}")
            analysis_text = str(analysis_text)

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
            "model_used": "o3-mini",
            "api_version": "responses_v1",  # Указываем новый API
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
        """Быстрая рекомендация через новый Responses API"""
        if not cars:
            return "Нет машин для анализа"

        try:
            cars_data = self._prepare_cars_data(cars[:5])
            input_text = f"""Ты автоэксперт на Кипре. Из этих автомобилей выбери ОДНУ лучшую покупку:

{cars_data}

Учти: климат Кипра, доступность сервиса, соотношение цена/качество.
Ответь одним предложением: "Рекомендую Автомобиль #X потому что [конкретная причина]"
"""

            # НОВЫЙ RESPONSES API для быстрых рекомендаций
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/responses",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    json={
                        "model": "o3-mini",
                        "input": input_text
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()
                    return self._extract_response_text(result)
                else:
                    logger.error(f"Quick recommendation API error: {response.status_code}")
                    return "Быстрый анализ недоступен"

        except Exception as e:
            logger.error(f"Quick recommendation error: {e}")
            return "Быстрый анализ недоступен"

    async def test_connection(self) -> Dict[str, Any]:
        """Тест подключения к новому Responses API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/responses",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    json={
                        "model": "o3-mini",
                        "input": "Тест подключения к новому API"
                    },
                    timeout=15.0
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "status": "success",
                        "model": "o3-mini",
                        "api_version": "responses_v1",
                        "response": self._extract_response_text(result)
                    }
                else:
                    return {
                        "status": "error",
                        "model": "o3-mini",
                        "api_version": "responses_v1",
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }

        except Exception as e:
            logger.error(f"Responses API connection test failed: {e}")
            return {
                "status": "error",
                "model": "o3-mini",
                "api_version": "responses_v1",
                "error": str(e)
            }

    async def get_available_models(self) -> List[str]:
        """Получает список доступных моделей через старый API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    models_data = response.json()
                    available = [model["id"] for model in models_data.get("data", [])
                                 if any(keyword in model["id"] for keyword in ['gpt', 'o3', 'o1'])]
                    return sorted(available)
                else:
                    return ["o3-mini"]

        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            return ["o3-mini"]