# app/services/openai_service.py - ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ
import httpx
from typing import List, Dict, Any
from app.config import settings
from app.models.car import Car
import logging
import asyncio
import re

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.base_url = "https://api.openai.com/v1"

    def _build_full_market_analysis_input(self, market_summary: Dict[str, Any], sample_cars: List[Car]) -> str:
        """Строит input для полного анализа рынка с УЛУЧШЕННЫМИ компетенциями"""

        system_context = """Ты эксперт-аналитик автомобильного рынка Кипра с 20-летним опытом, специализирующийся на поиске выгодных сделок.

🎯 ТВОЯ ГЛАВНАЯ МИССИЯ: Найти ЛУЧШИЕ ПРЕДЛОЖЕНИЯ для покупки

🧠 ТВОИ КОМПЕТЕНЦИИ:
• Автомобильный эксперт: знание типичных проблем каждой модели BMW, Mercedes, Audi
• Климатолог Кипра: понимание влияния жары +40°C и морской соли на автомобили
• Ценовой аналитик: определение справедливой стоимости с учетом года, пробега, состояния
• Детектив сделок: выявление признаков срочной продажи и скрытых проблем
• Переговорщик: понимание когда и как торговаться
• Техничесткий инспектор: оценка реальных затрат на обслуживание в условиях Кипра

🔥 ОСОБЕННОСТИ КИПРСКОГО РЫНКА:
• Высокие температуры 35-45°C (кондиционеры работают на пределе!)
• Морская соль (коррозия металла, электроники)
• Малые расстояния (низкий пробег может быть обманчив)
• Дорогие запчасти (+30-50% к европейским ценам)
• Ограниченный выбор сервисов

🕵️ АНАЛИЗ ОПИСАНИЙ - КЛЮЧ К СДЕЛКАМ:
ЭТО КРИТИЧЕСКИ ВАЖНО! Внимательно читай каждое описание:

ПРИЗНАКИ ВЫГОДНОЙ СДЕЛКИ:
✅ "срочно", "urgent", "quick sale", "moving abroad"
✅ "one owner", "lady driven", "garage kept"  
✅ "full service history", "official dealer service"
✅ "no accidents", "accident free"
✅ "new tires", "new battery", "fresh MOT"
✅ "price negotiable", "open to offers"

КРАСНЫЕ ФЛАГИ:
⚠️ "minor work needed", "needs TLC", "project car"
⚠️ "selling as seen", "no warranty", "spares or repair"
⚠️ "high mileage but runs well" (обычно проблемы)
⚠️ отсутствие описания или очень краткое

🎯 КРИТЕРИИ ЛУЧШИХ ПРЕДЛОЖЕНИЙ:
1. Цена на 15-25% ниже рыночной
2. Четкие признаки срочности продажи
3. Один-два владельца максимум
4. Полная сервисная история (особенно кондиционер!)
5. Надежные модели для жаркого климата
6. Низкие затраты на обслуживание
7. Никаких скрытых проблем в описании

ОБЯЗАТЕЛЬНО: В конце указывай конкретные ID машин в формате: РЕКОМЕНДУЕМЫЕ_ID: [12, 25, 33, 41, 52, 68, 71, 89, 95, 103]"""

        # Подготавливаем сводку по рынку
        brands_info = []
        for brand, data in market_summary["brands_summary"].items():
            avg_year = f"{data['avg_year']:.0f}" if data['avg_year'] else 'н/д'
            avg_mileage = f"{data['avg_mileage']:,.0f}" if data['avg_mileage'] else 'н/д'
            brands_info.append(
                f"• {brand}: {data['count']} машин, средний год: {avg_year}, средний пробег: {avg_mileage} км")
        brands_info = "\n".join(brands_info)

        # Примеры машин для детального анализа (с акцентом на описания)
        sample_cars_info = []
        for i, car in enumerate(sample_cars[:25], 1):  # Увеличили до 25 для лучшего выбора
            price_clean = car.price.replace('€', '').replace(',', '').replace(' ', '').strip() if car.price else 'н/д'
            price_euro = f" ({int(price_clean):,} €)" if price_clean.isdigit() else ""

            # КРИТИЧЕСКИ ВАЖНО: Полное описание для поиска сделок
            description_analysis = ""
            if car.description and car.description.strip():
                desc_clean = car.description.strip()[:600]  # Увеличили до 600 символов

                # Анализируем признаки срочности
                urgent_indicators = self._detect_urgency_indicators(desc_clean)
                condition_indicators = self._detect_condition_indicators(desc_clean)

                description_analysis = f"""
📝 ОПИСАНИЕ ПРОДАВЦА (АНАЛИЗИРУЙ ВНИМАТЕЛЬНО!):
"{desc_clean}{'...' if len(car.description) > 600 else ''}"

🔍 ИНДИКАТОРЫ СДЕЛКИ:
• Срочность: {urgent_indicators}
• Состояние: {condition_indicators}
• Длина описания: {'подробное' if len(car.description) > 100 else 'краткое'}

❗ ЗАДАЧА: Определи это ВЫГОДНАЯ СДЕЛКА или обычное предложение?"""
            else:
                description_analysis = "❌ НЕТ ОПИСАНИЯ - ОСТОРОЖНО! Отсутствие описания часто скрывает проблемы"

            sample_cars_info.append(f"""
{'=' * 60}
🚗 АВТОМОБИЛЬ #{i} - ID: {car.id} - ДЕТАЛЬНЫЙ РАЗБОР
{'=' * 60}

🔢 БАЗОВЫЕ ДАННЫЕ:
• Модель: {car.title}
• Марка: {car.brand} ({car.year or 'год не указан'})
• Пробег: {f"{car.mileage:,} км" if car.mileage else 'не указан'}  
• Цена: {car.price}{price_euro}
• Локация: {car.place}
• Опции: {(car.features or 'не указаны')[:200]}
• Ссылка: {car.link}

{description_analysis}

💡 ТВОЯ ЗАДАЧА: Оцени этот автомобиль как ПОТЕНЦИАЛЬНУЮ СДЕЛКУ!
""")

        return f"""{system_context}

{'=' * 80}
📊 АНАЛИЗ КИПРСКОГО АВТОРЫНКА - ПОИСК ЛУЧШИХ СДЕЛОК  
{'=' * 80}

📈 ОБЩАЯ СТАТИСТИКА:
• Всего машин в базе: {market_summary["total_cars"]}
• Диапазон годов: {market_summary["year_range"]}
• Диапазон пробега: {market_summary["mileage_range"]}
• Ценовой диапазон: {market_summary["price_range"]}
• Количество брендов: {market_summary["brands_count"]}

🏷️ РАЗБИВКА ПО БРЕНДАМ:
{brands_info}

{''.join(sample_cars_info)}

{'=' * 80}
🎯 ПРОВЕДИ ЭКСПЕРТНЫЙ АНАЛИЗ ДЛЯ ПОИСКА СДЕЛОК:
{'=' * 80}

**СОСТОЯНИЕ РЫНКА:**
Общая оценка текущего рынка, какие сегменты наиболее привлекательны

**АНАЛИЗ ПО БРЕНДАМ:**
Для каждого бренда:
- Представленность и конкурентоспособность цен
- Надежность в условиях Кипра (жара, соль)
- Средние затраты на обслуживание
- Лучшие модели и годы

**🏆 ТОП-10 ЛУЧШИХ СДЕЛОК (ГЛАВНОЕ!):**
Выбери 10 самых выгодных автомобилей, ОБЯЗАТЕЛЬНО учитывая:

Для каждой машины указывай:
1. ID автомобиля и краткое название
2. Почему это СДЕЛКА (цена, срочность, состояние)
3. Анализ описания - что говорит о мотивах продажи?
4. Ожидаемые затраты на обслуживание
5. Риски и красные флаги
6. Финальная рекомендация (ПОКУПАТЬ/ТОРГОВАТЬСЯ/ОСМОТРЕТЬ)

**🔍 НАХОДКИ В ОПИСАНИЯХ:**
Какие машины показывают признаки:
- Срочной продажи (переезд, финансовые проблемы)
- Отличного ухода (один владелец, сервис)
- Скрытых проблем (уклончивые формулировки)

**💰 СТРАТЕГИЯ ПОКУПКИ:**
Конкретные советы для текущего рынка

КРИТИЧЕСКИ ВАЖНО: В самом конце укажи ID рекомендованных машин в формате:
РЕКОМЕНДУЕМЫЕ_ID: [12, 25, 33, 41, 52, 68, 71, 89, 95, 103]

ПОМНИ: Ищи РЕАЛЬНУЮ ВЫГОДУ, не просто хорошие машины!"""

    def _detect_urgency_indicators(self, text: str) -> str:
        """Определяет индикаторы срочности в тексте"""
        if not text:
            return "не обнаружены"

        text_lower = text.lower()
        urgent_keywords = [
            "срочно", "urgent", "quick sale", "быстро", "asap", "must sell",
            "moving", "relocating", "emigrating", "leaving", "переезд",
            "price drop", "reduced", "negotiable", "торг", "снижена цена"
        ]

        found = [kw for kw in urgent_keywords if kw in text_lower]
        return ", ".join(found) if found else "не обнаружены"

    def _detect_condition_indicators(self, text: str) -> str:
        """Определяет индикаторы состояния в тексте"""
        if not text:
            return "не указаны"

        text_lower = text.lower()
        positive = ["excellent", "perfect", "отличное", "идеальное", "one owner",
                    "full service", "garage kept", "no accidents"]
        negative = ["needs work", "minor issues", "требует", "проблемы",
                    "spares or repair", "project car"]

        pos_found = [kw for kw in positive if kw in text_lower]
        neg_found = [kw for kw in negative if kw in text_lower]

        result = []
        if pos_found:
            result.append(f"✅ {', '.join(pos_found)}")
        if neg_found:
            result.append(f"⚠️ {', '.join(neg_found)}")

        return "; ".join(result) if result else "нейтральные"

    def _extract_recommended_car_ids(self, recommendations: str, cars: List[Car]) -> List[int]:
        """ИСПРАВЛЕННОЕ извлечение ID рекомендованных машин"""
        import re

        found_ids = set()

        # 1. Ищем специальный формат в конце: РЕКОМЕНДУЕМЫЕ_ID: [12, 25, 33]
        special_pattern = r'РЕКОМЕНДУЕМЫЕ_ID:\s*\[([0-9,\s]+)\]'
        special_match = re.search(special_pattern, recommendations)

        if special_match:
            ids_str = special_match.group(1)
            for id_str in ids_str.split(','):
                try:
                    car_id = int(id_str.strip())
                    if any(car.id == car_id for car in cars):
                        found_ids.add(car_id)
                except ValueError:
                    continue

        # 2. Если не найден специальный формат, ищем по старым паттернам
        if not found_ids:
            id_patterns = [
                r'① ID #?(\d+)',  # ① ID #10 или ① ID 10
                r'② ID #?(\d+)',  # ② ID #13
                r'③ ID #?(\d+)',  # ③ ID #14
                r'④ ID #?(\d+)',  # и так далее...
                r'⑤ ID #?(\d+)',
                r'⑥ ID #?(\d+)',
                r'⑦ ID #?(\d+)',
                r'⑧ ID #?(\d+)',
                r'⑨ ID #?(\d+)',
                r'⑩ ID #?(\d+)',
                r'ID[:\s#]+(\d+)',  # ID: 123, ID #123, ID 123
                r'Автомобиль #(\d+)',
                r'машин[аы]\s+#?(\d+)',
                r'\(ID:\s*(\d+)\)'
            ]

            for pattern in id_patterns:
                matches = re.findall(pattern, recommendations, re.IGNORECASE)
                for match in matches:
                    try:
                        car_id = int(match)
                        if any(car.id == car_id for car in cars):
                            found_ids.add(car_id)
                    except ValueError:
                        continue

        logger.info(f"Извлечено рекомендованных ID: {sorted(list(found_ids))}")
        return sorted(list(found_ids))

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

    async def analyze_full_market(self, all_cars: List[Car], brands_stats: Dict[str, List[Car]]) -> Dict[str, Any]:
        """🎯 ГЛАВНЫЙ МЕТОД: Анализ всего рынка с улучшенными компетенциями"""

        if not all_cars:
            return {"error": "Нет машин для анализа", "total_cars_analyzed": 0}

        # Подготавливаем данные для анализа
        market_summary = self._prepare_market_summary(all_cars, brands_stats)
        input_text = self._build_full_market_analysis_input(market_summary, all_cars[:25])

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
                    timeout=120.0
                )

                if response.status_code != 200:
                    raise Exception(f"API Error {response.status_code}: {response.text}")

                result = response.json()

                # Проверяем статус и ждем завершения если нужно
                status = result.get("status", "unknown")
                logger.info(f"API response status: {status}")

                if status == "in_progress":
                    response_id = result.get("id")
                    if response_id:
                        logger.info(f"Response in progress, waiting for completion: {response_id}")
                        for attempt in range(30):
                            await asyncio.sleep(10)

                            check_response = await client.get(
                                f"{self.base_url}/responses/{response_id}",
                                headers={"Authorization": f"Bearer {self.api_key}"},
                                timeout=30.0
                            )

                            if check_response.status_code == 200:
                                check_result = check_response.json()
                                check_status = check_result.get("status", "unknown")
                                logger.info(f"Check attempt {attempt + 1}: {check_status}")

                                if check_status == "completed":
                                    result = check_result
                                    break
                                elif check_status in ["failed", "cancelled"]:
                                    error = check_result.get("error", "Unknown error")
                                    raise Exception(f"Analysis failed: {error}")
                        else:
                            raise Exception("Analysis timeout after 5 minutes")

                analysis_text = self._extract_response_text(result)

                if len(analysis_text) < 100:
                    raise Exception(f"Response too short: {analysis_text}")

                return self._parse_full_market_analysis(analysis_text, all_cars, brands_stats)

        except Exception as e:
            logger.error(f"❌ Full market analysis error: {e}")
            raise Exception(f"Ошибка AI анализа рынка: {str(e)}")

    def _extract_response_text(self, api_response: Dict) -> str:
        """Извлекает текст из ответа API (улучшенная версия)"""
        try:
            logger.info(f"API Response structure: {list(api_response.keys())}")

            # Проверяем основные поля ответа
            if "output" in api_response:
                output = api_response["output"]
                logger.info(f"Output type: {type(output)}")

                if isinstance(output, list) and len(output) > 0:
                    for i, output_item in enumerate(output):
                        logger.info(
                            f"Output item {i}: {type(output_item)} - {list(output_item.keys()) if isinstance(output_item, dict) else 'not dict'}")

                        if isinstance(output_item, dict):
                            item_type = output_item.get("type", "unknown")
                            logger.info(f"Item type: {item_type}")

                            if item_type == "message":
                                if "content" in output_item:
                                    content_array = output_item["content"]
                                    logger.info(
                                        f"Content array type: {type(content_array)}, length: {len(content_array) if isinstance(content_array, list) else 'not list'}")

                                    if isinstance(content_array, list) and len(content_array) > 0:
                                        for j, content_item in enumerate(content_array):
                                            logger.info(
                                                f"Content item {j}: {type(content_item)} - {list(content_item.keys()) if isinstance(content_item, dict) else content_item}")

                                            if isinstance(content_item, dict) and "text" in content_item:
                                                text_value = content_item["text"]
                                                logger.info(f"Found text: {len(str(text_value))} characters")
                                                return str(text_value)
                elif isinstance(output, str):
                    return output

            # Проверяем поле 'reasoning' если есть
            if "reasoning" in api_response:
                reasoning = api_response["reasoning"]
                if isinstance(reasoning, str) and len(reasoning) > 50:
                    logger.info("Using reasoning field as response")
                    return reasoning

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
            logger.info(f"Found {len(long_strings)} long strings")

            for path, text in long_strings:
                logger.info(f"Long string at {path}: {len(text)} chars")

            if long_strings:
                return long_strings[0][1]

            # Если ничего не найдено, возвращаем структурированную ошибку
            return f"Не удалось извлечь текст из ответа API. Структура: {list(api_response.keys())}"

        except Exception as e:
            logger.error(f"Ошибка извлечения текста: {e}")
            return f"Ошибка обработки ответа: {str(e)}"

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

        # Убираем бюджетные автомобили
        budget_ids = {
            car.id for car in all_cars
            if (car.filter_name == "budget_urgent" or (car.brand and car.brand.lower() == "budget"))
        }
        recommended_ids = [cid for cid in recommended_ids if cid not in budget_ids]

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
                }
                for car in all_cars[:100]
                if car.id not in budget_ids
            ]
        }

    # ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ ДЛЯ ТРЕНДОВ И LEGACY
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

                if response.status_code != 200:
                    raise Exception(f"API Error {response.status_code}: {response.text}")

                result = response.json()

                # Проверяем статус и ждем завершения если нужно
                status = result.get("status", "unknown")
                if status == "in_progress":
                    response_id = result.get("id")
                    if response_id:
                        for attempt in range(18):  # 3 минуты для trends анализа
                            await asyncio.sleep(10)

                            check_response = await client.get(
                                f"{self.base_url}/responses/{response_id}",
                                headers={"Authorization": f"Bearer {self.api_key}"},
                                timeout=30.0
                            )

                            if check_response.status_code == 200:
                                check_result = check_response.json()
                                check_status = check_result.get("status", "unknown")

                                if check_status == "completed":
                                    result = check_result
                                    break
                                elif check_status in ["failed", "cancelled"]:
                                    error = check_result.get("error", "Unknown error")
                                    raise Exception(f"Trends analysis failed: {error}")

                analysis_text = self._extract_response_text(result)
                return self._parse_trends_analysis(analysis_text, all_cars, recent_cars)

        except Exception as e:
            logger.error(f"❌ Trends analysis error: {e}")
            raise Exception(f"Ошибка анализа трендов: {str(e)}")

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

    # LEGACY МЕТОДЫ (для обратной совместимости)
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
                    timeout=90.0
                )

                if response.status_code != 200:
                    raise Exception(f"API Error {response.status_code}: {response.text}")

                result = response.json()

                # Ждем завершения если нужно
                status = result.get("status", "unknown")
                if status == "in_progress":
                    response_id = result.get("id")
                    if response_id:
                        for attempt in range(18):  # 3 минуты для legacy анализа
                            await asyncio.sleep(10)

                            check_response = await client.get(
                                f"{self.base_url}/responses/{response_id}",
                                headers={"Authorization": f"Bearer {self.api_key}"},
                                timeout=30.0
                            )

                            if check_response.status_code == 200:
                                check_result = check_response.json()
                                check_status = check_result.get("status", "unknown")

                                if check_status == "completed":
                                    result = check_result
                                    break
                                elif check_status in ["failed", "cancelled"]:
                                    error = check_result.get("error", "Unknown error")
                                    raise Exception(f"Legacy analysis failed: {error}")

                analysis_text = self._extract_response_text(result)
                return self._parse_analysis_response(analysis_text, cars)

        except Exception as e:
            logger.error(f"❌ Legacy analyze_cars error: {e}")
            raise Exception(f"Ошибка AI анализа: {str(e)}")

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

    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
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
                    timeout=60.0
                )

                if response.status_code == 200:
                    result = response.json()

                    # Для быстрой рекомендации ждем меньше времени
                    status = result.get("status", "unknown")
                    if status == "in_progress":
                        response_id = result.get("id")
                        if response_id:
                            for attempt in range(6):  # 1 минута для быстрой рекомендации
                                await asyncio.sleep(10)

                                check_response = await client.get(
                                    f"{self.base_url}/responses/{response_id}",
                                    headers={"Authorization": f"Bearer {self.api_key}"},
                                    timeout=30.0
                                )

                                if check_response.status_code == 200:
                                    check_result = check_response.json()
                                    check_status = check_result.get("status", "unknown")

                                    if check_status == "completed":
                                        result = check_result
                                        break
                                    elif check_status in ["failed", "cancelled"]:
                                        return "Быстрый анализ не удался"

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
                        "input": "Ответь одним словом: 'Тест'"
                    },
                    timeout=60.0
                )

                if response.status_code == 200:
                    result = response.json()
                    status = result.get("status", "unknown")

                    if status == "in_progress":
                        # Ждем завершения для теста
                        response_id = result.get("id")
                        if response_id:
                            for attempt in range(12):  # 2 минуты ожидания для простого теста
                                await asyncio.sleep(10)

                                check_response = await client.get(
                                    f"{self.base_url}/responses/{response_id}",
                                    headers={"Authorization": f"Bearer {self.api_key}"},
                                    timeout=30.0
                                )

                                if check_response.status_code == 200:
                                    check_result = check_response.json()
                                    check_status = check_result.get("status", "unknown")

                                    if check_status == "completed":
                                        result = check_result
                                        break
                                    elif check_status in ["failed", "cancelled"]:
                                        error = check_result.get("error", "Unknown error")
                                        return {
                                            "status": "error",
                                            "model": "o3-mini",
                                            "error": f"Test failed: {error}"
                                        }

                    response_text = self._extract_response_text(result)
                    return {
                        "status": "success",
                        "model": "o3-mini",
                        "api_version": "responses_v1",
                        "response": response_text,
                        "api_status": result.get("status", "unknown")
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
                    timeout=60.0,
                )

                if response.status_code == 200:
                    result = response.json()

                    # Для простого вопроса ждем недолго
                    status = result.get("status", "unknown")
                    if status == "in_progress":
                        response_id = result.get("id")
                        if response_id:
                            for attempt in range(6):  # 1 минута для urgent detection
                                await asyncio.sleep(10)

                                check_response = await client.get(
                                    f"{self.base_url}/responses/{response_id}",
                                    headers={"Authorization": f"Bearer {self.api_key}"},
                                    timeout=30.0
                                )

                                if check_response.status_code == 200:
                                    check_result = check_response.json()
                                    check_status = check_result.get("status", "unknown")

                                    if check_status == "completed":
                                        result = check_result
                                        break
                                    elif check_status in ["failed", "cancelled"]:
                                        return False  # Если анализ не удался, считаем не urgent

                    answer = self._extract_response_text(result).lower()
                    return "yes" in answer or "да" in answer
        except Exception as e:
            logger.error(f"Urgent sale detection failed: {e}")
        return False