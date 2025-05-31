# app/services/scraper_service.py - ОБНОВЛЕННЫЙ с парсингом деталей
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import re
import time
import json
from typing import List, Dict, Optional
from app.config import settings
from app.schemas.car import CarCreate, CarDetailUpdate
import logging

logger = logging.getLogger(__name__)


class ScraperService:
    def __init__(self):
        self.options = Options()
        self.options.add_argument('--headless')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')

    def _create_driver(self) -> webdriver.Chrome:
        return webdriver.Chrome(options=self.options)

    def _parse_car_data(self, ad, filter_config: Dict) -> Optional[CarCreate]:
        """Парсит основную информацию с главной страницы"""
        # Title и link
        title_tag = ad.find("a", class_="advert__content-title")
        if not title_tag:
            return None

        title = title_tag.text.strip()
        link = "https://www.bazaraki.com" + title_tag.get('href', '')

        # Price
        price_tag = ad.find("a", class_="advert__content-price")
        price = price_tag.text.strip().replace("\n", " ") if price_tag else "нет цены"

        # Parse features
        features_tag = ad.find("div", class_="advert__content-features")
        features = []
        mileage = None
        year = None

        if features_tag:
            for f in features_tag.find_all("div", class_="advert__content-feature"):
                text = f.text.strip()
                features.append(text)

                # Parse mileage
                mileage_match = re.search(r'([\d,. ]+)\s*km', text.lower())
                if mileage_match:
                    mileage_str = mileage_match.group(1).replace(',', '').replace(' ', '')
                    try:
                        mileage = int(mileage_str)
                    except:
                        pass

                # Parse year
                year_match = re.search(r'(19\d{2}|20\d{2})', text)
                if year_match:
                    try:
                        year = int(year_match.group(1))
                    except:
                        pass

        # Parse year from title if not found
        if year is None:
            title_year_match = re.search(r'(19\d{2}|20\d{2})', title)
            if title_year_match:
                try:
                    year = int(title_year_match.group(1))
                except:
                    pass

        # Date and place
        hint_tag = ad.find("div", class_="advert__content-hint")
        date_posted, place = "нет даты", "нет города"

        if hint_tag:
            date_tag = hint_tag.find("div", class_="advert__content-date")
            if date_tag:
                date_posted = date_tag.text.strip()

            place_tag = hint_tag.find("div", class_="advert__content-place")
            if place_tag:
                place = place_tag.text.strip()

        # Apply filters
        if year and year < filter_config.get("min_year", 0):
            return None

        if mileage and mileage > filter_config.get("max_mileage", float('inf')):
            return None

        return CarCreate(
            title=title,
            link=link,
            price=price,
            brand=filter_config["brand"],
            year=year,
            mileage=mileage,
            features=' | '.join(features) if features else "нет данных",
            date_posted=date_posted,
            place=place,
            filter_name=filter_config.get("filter_name", "unknown"),
            details_parsed=False  # Пока детали не парсились
        )

    def parse_car_details(self, driver: webdriver.Chrome, car_url: str) -> CarDetailUpdate:
        """🔍 Парсит детальную страницу автомобиля"""
        try:
            logger.info(f"Парсинг деталей: {car_url}")
            driver.get(car_url)
            time.sleep(3)  # Даем странице загрузиться

            soup = BeautifulSoup(driver.page_source, "html.parser")
            details = {}
            extra_chars = {}

            # === ПАРСИНГ ХАРАКТЕРИСТИК ИЗ ТАБЛИЦЫ ===
            characteristics_div = soup.find("div", class_="announcement-characteristics clearfix")
            if characteristics_div:
                ul = characteristics_div.find("ul", class_="chars-column")
                if ul:
                    for li in ul.find_all("li"):
                        key_span = li.find("span", class_="key-chars")
                        value_tag = li.find("a", class_="value-chars") or li.find("span", class_="value-chars")

                        if key_span and value_tag:
                            key = key_span.text.strip(': \n').lower()
                            value = value_tag.text.strip()

                            # Маппинг известных полей
                            field_mapping = {
                                'mot till': 'mot_till',
                                'colour': 'colour',
                                'color': 'colour',
                                'gearbox': 'gearbox',
                                'fuel type': 'fuel_type',
                                'engine size': 'engine_size',
                                'doors': 'doors',
                                'seats': 'seats',
                                'condition': 'condition',
                                'previous owners': 'previous_owners',
                                'registration': 'registration',
                                'import duty paid': 'import_duty_paid',
                                'roadworthy certificate': 'roadworthy_certificate'
                            }

                            mapped_field = field_mapping.get(key)
                            if mapped_field:
                                details[mapped_field] = value
                            else:
                                # Сохраняем в extra_characteristics
                                extra_chars[key] = value

            # === ПАРСИНГ ОПИСАНИЯ ===
            description = ""

            # Пробуем разные селекторы для описания
            description_selectors = [
                "div.js-description",
                "div[itemprop='description']",
                "div.announcement-description",
                "div.description-text"
            ]

            for selector in description_selectors:
                desc_div = soup.select_one(selector)
                if desc_div:
                    description = desc_div.get_text(strip=True)
                    break

            # === ОПРЕДЕЛЕНИЕ ТИПА ПРОДАВЦА ===
            seller_type = "unknown"

            # Ищем индикаторы дилера
            dealer_indicators = soup.find_all(text=re.compile(r'dealer|дилер|garage|автосалон', re.I))
            if dealer_indicators:
                seller_type = "dealer"
            else:
                seller_type = "private"

            # === КОНТАКТНАЯ ИНФОРМАЦИЯ ===
            contact_info = ""

            contact_div = soup.find("div", class_="announcement-contact")
            if contact_div:
                contact_info = contact_div.get_text(strip=True)

            # Формируем объект для обновления
            detail_update = CarDetailUpdate(
                mot_till=details.get('mot_till'),
                colour=details.get('colour'),
                gearbox=details.get('gearbox'),
                fuel_type=details.get('fuel_type'),
                engine_size=details.get('engine_size'),
                doors=details.get('doors'),
                seats=details.get('seats'),
                condition=details.get('condition'),
                previous_owners=details.get('previous_owners'),
                registration=details.get('registration'),
                import_duty_paid=details.get('import_duty_paid'),
                roadworthy_certificate=details.get('roadworthy_certificate'),
                description=description if description else None,
                seller_type=seller_type,
                contact_info=contact_info if contact_info else None,
                extra_characteristics=json.dumps(extra_chars, ensure_ascii=False) if extra_chars else None,
                details_parsed=True
            )

            logger.info(
                f"✅ Детали успешно парсированы: {len(details)} основных полей, {len(extra_chars)} дополнительных")
            return detail_update

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга деталей {car_url}: {e}")
            # Возвращаем минимальный объект с флагом ошибки
            return CarDetailUpdate(
                details_parsed=False,
                description=f"Ошибка парсинга: {str(e)}"
            )

    async def scrape_cars(self, filter_name: str) -> List[CarCreate]:
        """Основной метод скрапинга с главной страницы"""
        filter_config = settings.car_filters.get(filter_name)
        if not filter_config:
            return []

        filter_config["filter_name"] = filter_name

        driver = self._create_driver()
        try:
            driver.get(filter_config["url"])
            time.sleep(5)

            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            ads = soup.find_all("div", class_="advert js-item-listing")

            cars = []
            for ad in ads:
                car_data = self._parse_car_data(ad, filter_config)
                if car_data:
                    cars.append(car_data)

            logger.info(f"Найдено {len(cars)} машин для фильтра {filter_name}")
            return cars

        finally:
            driver.quit()

    async def scrape_car_details_batch(self, car_links: List[str], batch_size: int = 5) -> List[CarDetailUpdate]:
        """🔄 Пакетный парсинг деталей для списка машин"""

        if not car_links:
            return []

        results = []
        driver = self._create_driver()

        try:
            logger.info(f"Начинаем пакетный парсинг деталей для {len(car_links)} машин")

            for i, link in enumerate(car_links):
                try:
                    detail_update = self.parse_car_details(driver, link)
                    results.append(detail_update)

                    # Пауза между запросами
                    if i < len(car_links) - 1:
                        time.sleep(2)

                    # Прогресс
                    if (i + 1) % 5 == 0:
                        logger.info(f"Парсинг деталей: {i + 1}/{len(car_links)}")

                except Exception as e:
                    logger.error(f"Ошибка парсинга деталей для {link}: {e}")
                    results.append(CarDetailUpdate(details_parsed=False))

            logger.info(f"✅ Пакетный парсинг завершен: {len(results)} результатов")
            return results

        finally:
            driver.quit()

    async def scrape_cars_with_details(self, filter_name: str, parse_details: bool = True) -> List[CarCreate]:
        """🚀 Полный скрапинг: основная информация + детали"""

        # Сначала получаем основную информацию
        cars = await self.scrape_cars(filter_name)

        if not cars or not parse_details:
            return cars

        # Затем парсим детали для каждой машины
        logger.info(f"Запускаем парсинг деталей для {len(cars)} машин...")

        driver = self._create_driver()

        try:
            for i, car in enumerate(cars):
                try:
                    detail_update = self.parse_car_details(driver, car.link)

                    # Обновляем основной объект детальными данными
                    for field, value in detail_update.dict(exclude_unset=True).items():
                        if hasattr(car, field) and value is not None:
                            setattr(car, field, value)

                    time.sleep(2)  # Пауза между запросами

                    if (i + 1) % 3 == 0:
                        logger.info(f"Детали парсированы: {i + 1}/{len(cars)}")

                except Exception as e:
                    logger.error(f"Ошибка парсинга деталей для {car.title}: {e}")
                    # Помечаем что парсинг не удался
                    car.details_parsed = False

            logger.info(f"✅ Полный скрапинг завершен для {filter_name}")
            return cars

        finally:
            driver.quit()