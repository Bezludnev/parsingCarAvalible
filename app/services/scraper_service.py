# app/services/scraper_service.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re
import asyncio
from typing import List, Dict, Optional
from app.config import settings
from app.schemas.car import CarCreate
import httpx


class ScraperService:
    def __init__(self):
        self.options = Options()
        self.options.add_argument('--headless')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')

    def _fetch_description(self, link: str) -> Optional[str]:
        """Загружает страницу объявления и извлекает описание"""
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(link)
                if resp.status_code != 200:
                    return None
                soup = BeautifulSoup(resp.text, 'html.parser')
                desc_div = soup.find('div', class_='js-description')
                if desc_div:
                    paragraphs = [p.get_text(' ', strip=True) for p in desc_div.find_all('p')]
                    return ' '.join(paragraphs)
        except Exception:
            return None

        return None

    def _create_driver(self) -> webdriver.Chrome:
        """Create Chrome driver using path from settings"""
        service = Service(executable_path=settings.chromedriver_path)
        return webdriver.Chrome(service=service, options=self.options)

    def _parse_car_data(self, ad, filter_config: Dict) -> Optional[CarCreate]:
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

        # Description
        desc_tag = ad.find("div", class_="advert__description")
        if not desc_tag:
            desc_tag = ad.find("div", class_="advert__content-description")
        description = desc_tag.text.strip() if desc_tag else None
        if not description:
            description = self._fetch_description(link)

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
            description=description,
            date_posted=date_posted,
            place=place,
            filter_name=filter_config.get("filter_name", "unknown")
        )

    def _scrape_cars_sync(self, filter_config: Dict) -> List[CarCreate]:
        """Synchronous scraping logic executed in a thread"""

        driver = self._create_driver()
        try:
            driver.get(filter_config["url"])
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.advert.js-item-listing")
                )
            )

            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            ads = soup.find_all("div", class_="advert js-item-listing")

            cars = []
            for ad in ads:
                car_data = self._parse_car_data(ad, filter_config)
                if car_data:
                    cars.append(car_data)

            return cars

        finally:
            driver.quit()

    async def scrape_cars(self, filter_name: str) -> List[CarCreate]:
        """Public async method that offloads work to a thread"""

        filter_config = settings.car_filters.get(filter_name)
        if not filter_config:
            return []

        filter_config["filter_name"] = filter_name

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._scrape_cars_sync, filter_config)

