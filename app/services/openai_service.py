# app/services/openai_service.py - ОБНОВЛЕННАЯ для анализа всей базы
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

    async def analyze_full_market(self, all_cars: List[Car], brands_stats: Dict[str, List[Car]]) -> Dict[str, Any]:
        """🎯 ГЛАВНЫЙ МЕТОД: Анализ всего рынка одним запросом"""

        if not all_cars:
            return {"error": "Нет машин для анализа", "total_cars_analyzed": 0}

        # Подготавливаем данные для анализа
        market_summary = self._prepare_market_summary(all_cars, brands_stats)
        input_text = self._build_full_market_analysis_input(market_summary,
                                                            all_cars[:50])  # Топ-50 для детального анализа

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
                        "input": input_text
                    },
                    timeout=120.0  # Увеличиваем timeout для большого анализа
                )

                if response.status_code != 200:
                    raise Exception(f"API Error {response.status_code}: {response.text}")

                result = response.json()
                analysis_text = self._extract_response_text(result)

                return self._parse_full_market_analysis(analysis_text, all_cars, brands_stats)

        except Exception as e:
            logger.error(f"❌ Full market analysis error: {e}")
            raise Exception(f"Ошибка AI анализа рынка: {str(e)}")

    async def analyze_market_trends(self, all_cars: List[Car], recent_cars: List[Car], days: int) -> Dict[str, Any]:
        """📈 Анализ трендов рынка"""

        trends_data = self._prepare_trends_data(all_cars, recent_cars, days)
        input_text = self._build_trends_analysis_input(trends_data)

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
                        "input": input_text
                    },
                    timeout=90.0
                )

                if response.status_code == 200:
                    result = response.json()
                    analysis_text = self._extract_response_text(result)
                    return self._parse_trends_analysis(analysis_text, all_cars, recent_cars)
                else:
                    raise Exception(f"API Error {response.status_code}")

        except Exception as e:
            logger.error(f"❌ Trends analysis error: {e}")
            raise Exception(f"Ошибка анализа трендов: {str(e)}")

    def _prepare_market_summary(self, all_cars: List[Car], brands_stats: Dict[str, List[Car]]) -> Dict[str, Any]:
        """Подготавливает сводку по рынку"""

        # Общая статистика
        total_cars = len(all_cars)
        years = [car.year for car in all_cars if car.year]
        mileages = [car.mileage for car in all_cars if car.mileage]

        # Извлекаем цены
        prices = []
        for car in all_cars:
            if car.price:
                price_clean = car.price.replace('€', '').replace(',', '').replace(' ', '').strip()
                try:
                    if price_clean.isdigit():
                        prices.append(int(price_clean))
                except:
                    pass

        # Статистика по брендам
        brands_summary = {}
        for brand, cars in brands_stats.items():
            brands_summary[brand] = {
                "count": len(cars),
                "avg_year": sum(car.year for car in cars if car.year) / len([car for car in cars if car.year]) if any(
                    car.year for car in cars) else None,
                "avg_mileage": sum(car.mileage for car in cars if car.mileage) / len(
                    [car for car in cars if car.mileage]) if any(car.mileage for car in cars) else None
            }

        return {
            "total_cars": total_cars,
            "avg_year": sum(years) / len(years) if years else None,
            "year_range": f"{min(years)}-{max(years)}" if years else None,
            "avg_mileage": sum(mileages) / len(mileages) if mileages else None,
            "mileage_range": f"{min(mileages):,}-{max(mileages):,}" if mileages else None,
            "avg_price": sum(prices) / len(prices) if prices else None,
            "price_range": f"€{min(prices):,}-€{max(prices):,}" if prices else None,
            "brands_count": len(brands_stats),
            "brands_summary": brands_summary,
            "top_3_brands": sorted(brands_stats.items(), key=lambda x: len(x[1]), reverse=True)[:3]
        }

    def _prepare_trends_data(self, all_cars: List[Car], recent_cars: List[Car], days: int) -> Dict[str, Any]:
        """Подготавливает данные для анализа трендов"""

        # Группируем recent_cars по дням
        from collections import defaultdict
        daily_activity = defaultdict(int)

        for car in recent_cars:
            if car.created_at:
                date_str = car.created_at.strftime('%Y-%m-%d')
                daily_activity[date_str] += 1

        # Средняя активность
        avg_daily = len(recent_cars) / days if days > 0 else 0

        return {
            "total_in_db": len(all_cars),
            "recent_additions": len(recent_cars),
            "analysis_period": days,
            "avg_daily_additions": round(avg_daily, 1),
            "daily_breakdown": dict(daily_activity),
            "recent_vs_total_ratio": round(len(recent_cars) / len(all_cars) * 100, 1) if all_cars else 0
        }

    def _build_full_market_analysis_input(self, market_summary: Dict[str, Any], sample_cars: List[Car]) -> str:
        """Строит input для полного анализа рынка"""

        system_context = """Ты опытный аналитик автомобильного рынка Кипра с 15-летним опытом.

ТВОЯ ЗАДАЧА: Проанализировать ВЕСЬ рынок подержанных автомобилей на Кипре на основе полной базы данных.

ОСОБЕННОСТИ РЫНКА КИПРА:
- Высокие температуры (влияние на кондиционеры, резину, пластик)
- Морская соль (коррозия)  
- Малые расстояния (низкий пробег не всегда показатель)
- Дорогие запчасти и сервис
- Ограниченный выбор моделей

АНАЛИЗ ОПИСАНИЙ - КРИТИЧЕСКИ ВАЖНО:
- Ищи признаки срочной продажи ("срочно", "urgent", "переезд", "снижена цена")
- Обращай внимание на состояние ("отличное", "идеальное", "требует ремонта")
- Ищи упоминания сервисной истории ("регулярное ТО", "только официальный сервис")
- Отмечай дополнительное оборудование и модификации
- Выявляй скрытые проблемы ("торг уместен", "небольшие царапины", "косметический ремонт")

ПРИНЦИПЫ АНАЛИЗА:
- Честно оценивай состояние рынка
- Выделяй лучшие предложения по соотношению цена/качество
- Учитывай информацию из описаний для точной оценки
- Предупреждай о завышенных ценах и скрытых проблемах
- Рекомендуй конкретные машины по ID"""

        # Подготавливаем сводку по рынку
        brands_info = "\n".join([
            f"• {brand}: {data['count']} машин, средний год: {data['avg_year']:.0f if data['avg_year'] else 'н/д'}, средний пробег: {data['avg_mileage']:,.0f if data['avg_mileage'] else 'н/д'} км"
            for brand, data in market_summary["brands_summary"].items()
        ])

        # Примеры машин для детального анализа (топ-20)
        sample_cars_info = []
        for i, car in enumerate(sample_cars[:20], 1):
            price_clean = car.price.replace('€', '').replace(',', '').replace(' ', '').strip() if car.price else 'н/д'
            price_euro = f" ({int(price_clean):,} €)" if price_clean.isdigit() else ""

            # Добавляем описание для более точного анализа
            description_text = ""
            if car.description and car.description.strip():
                desc_clean = car.description.strip()[:300]  # Ограничиваем для краткости
                description_text = f"• Описание: {desc_clean}{'...' if len(car.description) > 300 else ''}"

            sample_cars_info.append(f"""
Машина #{i} (ID: {car.id}):
• {car.title}
• {car.brand} {car.year or 'н/д'} года
• Пробег: {f"{car.mileage:,} км" if car.mileage else 'н/д'}
• Цена: {car.price}{price_euro}
• Место: {car.place}
• Характеристики: {(car.features or 'н/д')[:100]}
{description_text}
""")

        return f"""{system_context}

ПОЛНАЯ СВОДКА ПО РЫНКУ:
📊 Всего машин в базе: {market_summary["total_cars"]}
📅 Годы выпуска: {market_summary["year_range"]}
🛣 Пробег: {market_summary["mileage_range"]}
💰 Цены: {market_summary["price_range"]}
🏷️ Представлено брендов: {market_summary["brands_count"]}

РАЗБИВКА ПО БРЕНДАМ:
{brands_info}

ТОП-20 МАШИН ДЛЯ ДЕТАЛЬНОГО АНАЛИЗА:
{"".join(sample_cars_info)}

ПРОВЕДИ КОМПЛЕКСНЫЙ АНАЛИЗ:

**СОСТОЯНИЕ РЫНКА:**
Общая оценка рынка, динамика, основные тренды

**АНАЛИЗ ПО БРЕНДАМ:**
Для каждого бренда оцени:
- Представленность на рынке
- Средние цены и их адекватность
- Типичные проблемы моделей
- Рекомендации по выбору

**ТОП-10 ЛУЧШИХ ПРЕДЛОЖЕНИЙ:**
Выбери 10 лучших машин по критериям:
1. Соотношение цена/качество
2. Надежность модели
3. Состояние для климата Кипра
4. Доступность сервиса и запчастей
5. АНАЛИЗ ОПИСАНИЙ (срочность, состояние, история)

**АНАЛИЗ ОПИСАНИЙ:**
Для каждой топ-машины проанализируй:
- Признаки срочной продажи в описании
- Упоминания о состоянии и сервисной истории
- Дополнительное оборудование из описания
- Возможные скрытые проблемы в формулировках

**ОБЩИЕ РЕКОМЕНДАЦИИ:**
Советы покупателям по текущему состоянию рынка

Укажи конкретные ID машин в рекомендациях!"""

    def _build_trends_analysis_input(self, trends_data: Dict[str, Any]) -> str:
        """Строит input для анализа трендов"""

        daily_info = "\n".join([
            f"• {date}: {count} машин"
            for date, count in sorted(trends_data["daily_breakdown"].items(), reverse=True)[:10]
        ])

        return f"""Ты аналитик автомобильного рынка Кипра. Проанализируй тренды активности:

ДАННЫЕ ЗА ПОСЛЕДНИЕ {trends_data["analysis_period"]} ДНЕЙ:
📊 Всего в базе: {trends_data["total_in_db"]} машин
📈 Новых за период: {trends_data["recent_additions"]} машин  
⚡ Средняя активность: {trends_data["avg_daily_additions"]} машин/день
📊 Доля новых: {trends_data["recent_vs_total_ratio"]}%

АКТИВНОСТЬ ПО ДНЯМ (последние 10):
{daily_info}

АНАЛИЗИРУЙ:
**ДИНАМИКА РЫНКА:**
- Растет или падает активность?
- Есть ли сезонные паттерны?
- Оценка здоровья рынка

**ТРЕНДЫ ЦЕН:**
- Движение цен вверх/вниз
- Влияние активности на цены

**ПРОГНОЗ:**
- Ожидания на ближайшие недели
- Рекомендации по времени покупки

**ВЫВОДЫ:**
Краткие выводы для покупателей"""

    def _parse_full_market_analysis(self, analysis_text: str, all_cars: List[Car], brands_stats: Dict) -> Dict[
        str, Any]:
        """Парсит результат полного анализа рынка"""

        if not isinstance(analysis_text, str):
            analysis_text = str(analysis_text)

        sections = analysis_text.split("**")

        market_overview = ""
        brand_analysis = ""
        top_recommendations = ""
        general_conclusions = ""

        for i, section in enumerate(sections):
            section_lower = section.lower()
            if "состояние рынка" in section_lower or "market" in section_lower:
                market_overview = sections[i + 1] if i + 1 < len(sections) else ""
            elif "анализ по брендам" in section_lower or "brands" in section_lower:
                brand_analysis = sections[i + 1] if i + 1 < len(sections) else ""
            elif "лучших предложений" in section_lower or "топ" in section_lower or "top" in section_lower:
                top_recommendations = sections[i + 1] if i + 1 < len(sections) else ""
            elif "рекомендации" in section_lower or "выводы" in section_lower:
                general_conclusions = sections[i + 1] if i + 1 < len(sections) else ""

        # Извлекаем рекомендованные ID
        recommended_ids = self._extract_recommended_car_ids(top_recommendations, all_cars)

        return {
            "total_cars_analyzed": len(all_cars),
            "market_overview": market_overview.strip(),
            "brand_analysis": brand_analysis.strip(),
            "top_recommendations": top_recommendations.strip(),
            "general_conclusions": general_conclusions.strip(),
            "full_analysis": analysis_text,
            "recommended_car_ids": recommended_ids,
            "model_used": "o3-mini",
            "api_version": "responses_v1",
            "brands_analyzed": list(brands_stats.keys()),
            "cars_data": [
                {
                    "id": car.id,
                    "title": car.title,
                    "brand": car.brand,
                    "year": car.year,
                    "price": car.price,
                    "mileage": car.mileage,
                    "link": car.link,
                    "description": car.description[:200] + "..." if car.description and len(
                        car.description) > 200 else car.description
                } for car in all_cars[:100]  # Ограничиваем для размера ответа
            ]
        }

    def _parse_trends_analysis(self, analysis_text: str, all_cars: List[Car], recent_cars: List[Car]) -> Dict[str, Any]:
        """Парсит результат анализа трендов"""

        sections = analysis_text.split("**")

        market_dynamics = ""
        price_trends = ""
        forecast = ""
        conclusions = ""

        for i, section in enumerate(sections):
            section_lower = section.lower()
            if "динамика" in section_lower:
                market_dynamics = sections[i + 1] if i + 1 < len(sections) else ""
            elif "тренды цен" in section_lower or "price" in section_lower:
                price_trends = sections[i + 1] if i + 1 < len(sections) else ""
            elif "прогноз" in section_lower:
                forecast = sections[i + 1] if i + 1 < len(sections) else ""
            elif "выводы" in section_lower:
                conclusions = sections[i + 1] if i + 1 < len(sections) else ""

        return {
            "total_cars_analyzed": len(all_cars),
            "recent_cars_count": len(recent_cars),
            "market_dynamics": market_dynamics.strip(),
            "price_trends": price_trends.strip(),
            "forecast": forecast.strip(),
            "conclusions": conclusions.strip(),
            "full_analysis": analysis_text,
            "model_used": "o3-mini"
        }

    # LEGACY методы для обратной совместимости
    async def analyze_cars(self, cars: List[Car]) -> Dict[str, Any]:
        """Legacy метод для анализа списка машин"""
        if not cars:
            return {"error": "Нет машин для анализа", "total_cars_analyzed": 0}

        cars_data = self._prepare_cars_data(cars)
        input_text = self._build_analysis_input(cars_data)

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
            logger.error(f"❌ Legacy analyze_cars error: {e}")
            raise Exception(f"Ошибка AI анализа: {str(e)}")

    def _extract_response_text(self, api_response: Dict) -> str:
        """Извлекает текст из ответа API (без изменений)"""
        try:
            logger.info(f"API Response structure: {list(api_response.keys())}")

            if "text" in api_response:
                text_value = api_response["text"]
                if isinstance(text_value, dict):
                    logger.info(f"Text dict content: {text_value}")
                else:
                    return str(text_value)

            if "output" in api_response:
                output = api_response["output"]
                if isinstance(output, list):
                    for i, output_item in enumerate(output):
                        if isinstance(output_item, dict):
                            item_type = output_item.get("type", "unknown")
                            if item_type == "message":
                                if "content" in output_item:
                                    content_array = output_item["content"]
                                    if isinstance(content_array, list) and len(content_array) > 0:
                                        for content_item in content_array:
                                            if isinstance(content_item, dict) and "text" in content_item:
                                                return str(content_item["text"])

            # Fallback - ищем любую длинную строку
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
            if long_strings:
                return long_strings[0][1]

            return str(api_response)

        except Exception as e:
            logger.error(f"Ошибка извлечения текста: {e}")
            return f"Ошибка обработки ответа: {str(e)}"

    def _extract_recommended_car_ids(self, recommendations: str, cars: List[Car]) -> List[int]:
        """Извлекает ID рекомендованных машин"""
        import re

        # Ищем паттерны типа "ID: 123", "Машина #1", "ID 456"
        id_patterns = [
            r'ID:\s*(\d+)',
            r'ID\s+(\d+)',
            r'Машина\s+#(\d+)',
            r'\(ID:\s*(\d+)\)',
            r'машин[аы]\s+(\d+)',
            r'#(\d+)'
        ]

        found_ids = set()

        for pattern in id_patterns:
            matches = re.findall(pattern, recommendations, re.IGNORECASE)
            for match in matches:
                try:
                    car_id = int(match)
                    # Проверяем что такой ID существует в нашем списке
                    if any(car.id == car_id for car in cars):
                        found_ids.add(car_id)
                except ValueError:
                    continue

        # Если не нашли ID, пробуем найти номера машин из нумерации
        if not found_ids:
            number_matches = re.findall(r'Машина #(\d+)', recommendations)
            for num_str in number_matches:
                try:
                    car_index = int(num_str) - 1
                    if 0 <= car_index < len(cars):
                        found_ids.add(cars[car_index].id)
                except (ValueError, IndexError):
                    continue

        return list(found_ids)

    # Остальные методы остаются без изменений
    def _prepare_cars_data(self, cars: List[Car]) -> str:
        """Подготавливает данные машин для анализа (legacy)"""
        cars_info = []
        for i, car in enumerate(cars, 1):
            price_clean = car.price.replace('€', '').replace(',', '').replace(' ',
                                                                              '').strip() if car.price else 'не указана'
            price_numeric = ""
            if price_clean.isdigit():
                price_numeric = f" ({int(price_clean):,} евро)"

            # Обрабатываем описание - важная информация для AI
            description_text = ""
            if car.description and car.description.strip():
                desc_clean = car.description.strip()[:400]  # Ограничиваем до 400 символов
                description_text = f"• Описание: {desc_clean}{'...' if len(car.description) > 400 else ''}"

            info = f"""
Автомобиль #{i} (ID: {car.id}):
• Модель: {car.title}
• Марка: {car.brand}
• Год выпуска: {car.year or 'не указан'}
• Пробег: {f"{car.mileage:,} км" if car.mileage else 'не указан'}
• Цена: {car.price}{price_numeric}
• Характеристики: {car.features[:250] if car.features else 'нет данных'}
• Местоположение: {car.place}
{description_text}
"""
            cars_info.append(info)
        return "\n".join(cars_info)

    def _build_analysis_input(self, cars_data: str) -> str:
        """Строит input для legacy анализа"""
        system_context = """Ты опытный автоэксперт с 20-летним стажем на европейском рынке подержанных автомобилей.

ТВОЯ ЭКСПЕРТИЗА:
- Знание типичных проблем каждой модели BMW, Mercedes, Audi, Volkswagen
- Понимание реальной стоимости обслуживания в Европе  
- Оценка соотношения цена/качество на рынке Кипра
- Прогноз износа по пробегу и году выпуска
- Особенности климата Кипра (жара, соль) и их влияние на автомобили"""

        return f"""{system_context}

ЗАДАЧА: Проанализируй эти автомобили для покупки на Кипре:

{cars_data}

СТРУКТУРА ОТВЕТА:
**ТОП-3 РЕКОМЕНДАЦИИ:**
1. Автомобиль #X - краткая причина
2. Автомобиль #Y - краткая причина  
3. Автомобиль #Z - краткая причина

**ДЕТАЛЬНЫЙ АНАЛИЗ:**
Для каждого автомобиля дай оценку

**ОБЩИЕ ВЫВОДЫ:**
Итоговые рекомендации"""

    def _parse_analysis_response(self, analysis_text: str, cars: List[Car]) -> Dict[str, Any]:
        """Парсит ответ legacy анализа"""
        if not isinstance(analysis_text, str):
            analysis_text = str(analysis_text)

        sections = analysis_text.split("**")
        top_recommendations = ""
        detailed_analysis = ""
        general_conclusions = ""

        for i, section in enumerate(sections):
            if "ТОП-3" in section or "TOP-3" in section:
                top_recommendations = sections[i + 1] if i + 1 < len(sections) else ""
            elif "ДЕТАЛЬНЫЙ" in section:
                detailed_analysis = sections[i + 1] if i + 1 < len(sections) else ""
            elif "ОБЩИЕ" in section or "ВЫВОДЫ" in section:
                general_conclusions = sections[i + 1] if i + 1 < len(sections) else ""

        recommended_ids = self._extract_recommended_car_ids(top_recommendations, cars)

        return {
            "total_cars_analyzed": len(cars),
            "top_recommendations": top_recommendations.strip(),
            "detailed_analysis": detailed_analysis.strip(),
            "general_conclusions": general_conclusions.strip(),
            "full_analysis": analysis_text,
            "recommended_car_ids": recommended_ids,
            "model_used": "o3-mini",
            "api_version": "responses_v1",
            "cars_data": [
                {
                    "id": car.id,
                    "title": car.title,
                    "brand": car.brand,
                    "year": car.year,
                    "price": car.price,
                    "mileage": car.mileage,
                    "link": car.link,
                    "description": car.description[:200] + "..." if car.description and len(
                        car.description) > 200 else car.description
                } for car in cars
            ]
        }

    async def get_quick_recommendation(self, cars: List[Car]) -> str:
        """Быстрая рекомендация (legacy)"""
        if not cars:
            return "Нет машин для анализа"

        try:
            cars_data = self._prepare_cars_data(cars[:5])
            input_text = f"""Ты автоэксперт на Кипре. Из этих автомобилей выбери ОДНУ лучшую покупку:

{cars_data}

ВАЖНО: Обращай особое внимание на ОПИСАНИЯ машин - там может быть информация о:
- Срочности продажи
- Реальном состоянии
- Дополнительном оборудовании
- Сервисной истории
- Скрытых проблемах

Ответь одним предложением: "Рекомендую Автомобиль #X потому что [конкретная причина с учетом описания]"
"""
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
                    return "Быстрый анализ недоступен"

        except Exception as e:
            logger.error(f"Quick recommendation error: {e}")
            return "Быстрый анализ недоступен"

    async def test_connection(self) -> Dict[str, Any]:
        """Тест подключения к API"""
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
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }

        except Exception as e:
            return {
                "status": "error",
                "model": "o3-mini",
                "error": str(e)
            }

    async def get_available_models(self) -> List[str]:
        """Получает список доступных моделей"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
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

    async def detect_urgent_sale(self, text: str) -> bool:
        """Определяет признаки срочной продажи"""
        if not text:
            return False
        try:
            prompt = f"Ответь 'yes' или 'no'. В тексте есть признаки срочной продажи?\n\n{text}"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/responses",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    json={"model": "o3-mini", "input": prompt},
                    timeout=20.0,
                )
                if response.status_code == 200:
                    result = response.json()
                    answer = self._extract_response_text(result).lower()
                    return "yes" in answer or "да" in answer
        except Exception as e:
            logger.error(f"Urgent sale detection failed: {e}")
        return False