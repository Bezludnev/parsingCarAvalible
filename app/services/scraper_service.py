# app/services/scraper_service.py - ИСПРАВЛЕН: добавлены импорты и метод для одной машины
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Set, Any
from app.config import settings
from app.schemas.car import CarCreate
import httpx
import logging

logger = logging.getLogger(__name__)


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
        self.options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.options.add_argument('--accept-language=en-US,en;q=0.9')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        return webdriver.Chrome(service=service, options=self.options)

    def _has_urgent_keywords(self, text: str) -> bool:
        """Проверяет наличие urgent ключевых слов в тексте"""
        if not text:
            return False

        urgent_keywords = [
            'срочно', 'urgent', 'быстро', 'asap', 'must sell', 'price drop',
            'reduced', 'negotiable', 'open to offers', 'торг', 'обмен',
            'выгодно', 'недорого', 'дешево', 'снижена цена', 'уместен торг'
        ]

        text_lower = text.lower()
        return any(keyword in text_lower for keyword in urgent_keywords)

    def _should_skip_ad(self, ad, existing_links: Set[str]) -> tuple[bool, str]:
        """🎯 Проверяет, нужно ли пропустить объявление"""
        title_tag = ad.find("a", class_="advert__content-title")
        if not title_tag:
            return True, "no_title_tag"

        link = "https://www.bazaraki.com" + title_tag.get('href', '')

        if link in existing_links:
            return True, "already_exists"

        return False, ""

    def _parse_car_data(self, ad, filter_config: Dict, existing_links: Set[str]) -> Optional[CarCreate]:
        """Парсит данные автомобиля с проверкой существования"""

        # Сначала быстрая проверка - есть ли уже в базе
        should_skip, reason = self._should_skip_ad(ad, existing_links)
        if should_skip:
            if reason == "already_exists":
                logger.debug("⏭️ Пропускаем существующее объявление")
            return None

        # Title и link (уже проверили в _should_skip_ad)
        title_tag = ad.find("a", class_="advert__content-title")
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

        # Description (загружается отдельно - только для новых объявлений!)
        desc_tag = ad.find("div", class_="advert__description")
        if not desc_tag:
            desc_tag = ad.find("div", class_="advert__content-description")
        description = desc_tag.text.strip() if desc_tag else None
        if not description:
            description = self._fetch_description(link)

        # 🔥 URGENT MODE LOGIC - более мягкие фильтры
        is_urgent_mode = filter_config.get("urgent_mode", False)

        if is_urgent_mode:
            # В urgent режиме проверяем ключевые слова
            has_urgent_text = self._has_urgent_keywords(title) or self._has_urgent_keywords(description)

            # Более мягкие ограничения для urgent
            if year and year < filter_config.get("min_year", 0):
                if year < (filter_config.get("min_year", 0) - 2):
                    return None

            if mileage and mileage > filter_config.get("max_mileage", float('inf')):
                max_allowed = filter_config.get("max_mileage", float('inf'))
                if has_urgent_text:
                    max_allowed += 50000  # Бонус для urgent объявлений
                if mileage > max_allowed:
                    return None

            logger.info(f"🔥 Urgent режим: {filter_config.get('filter_name')} - найдена машина"
                        f" {'(URGENT keywords!)' if has_urgent_text else ''}")
        else:
            # Обычная логика фильтрации
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

    def _scrape_cars_sync(self, filter_config: Dict, existing_links: Set[str]) -> List[CarCreate]:
        """Synchronous scraping с оптимизацией по existing_links"""
        is_urgent = filter_config.get("urgent_mode", False)
        filter_name = filter_config.get("filter_name", "unknown")

        logger.info(f"🌐 Начинаем оптимизированный скрапинг: {filter_name} "
                    f"{'(URGENT режим)' if is_urgent else '(обычный режим)'}")
        logger.info(f"📋 Исключаем {len(existing_links)} существующих ссылок")

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
            debug_file = f"/app/debug_{filter_name}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"🐛 DEBUG: HTML сохранен в {debug_file}")
            # 🐛 ПРОСТОЙ ДЕБАГ
            filter_name = filter_config.get("filter_name", "unknown")
            logger.info(f"🐛 DEBUG {filter_name}: HTML размер={len(html)} символов")
            logger.info(f"🐛 DEBUG {filter_name}: div элементов всего={len(soup.find_all('div'))}")

            # Проверяем разные селекторы для объявлений:
            selectors = [
                ("div.advert.js-item-listing", "advert js-item-listing"),
                ("div.advert", "advert"),
                ("[class*='advert']", None),
                (".announcement-item", "announcement-item"),
            ]

            for selector, class_name in selectors:
                if class_name:
                    found = soup.find_all("div", class_=class_name)
                else:
                    found = soup.select(selector)
                logger.info(f"🐛 DEBUG {filter_name}: '{selector}' найдено {len(found)} элементов")

            # Проверяем ссылки на авто:
            all_links = soup.find_all('a', href=True)
            car_links = [a for a in all_links if 'bazaraki.com/adv/' in a.get('href', '')]
            logger.info(f"🐛 DEBUG {filter_name}: всего ссылок={len(all_links)}, на авто={len(car_links)}")

            # Проверяем заголовок страницы:
            title = soup.find('title')
            page_title = title.text[:100] if title else "нет заголовка"
            logger.info(f"🐛 DEBUG {filter_name}: заголовок='{page_title}'")

            ads = soup.select("div.advert.js-item-listing")
            logger.info(f"📄 Найдено {len(ads)} объявлений на странице для {filter_name}")

            cars = []
            skipped_existing = 0

            for ad in ads:
                car_data = self._parse_car_data(ad, filter_config, existing_links)
                if car_data:
                    cars.append(car_data)
                else:
                    # Проверяем причину пропуска
                    should_skip, reason = self._should_skip_ad(ad, existing_links)
                    if reason == "already_exists":
                        skipped_existing += 1

            logger.info(f"✅ Отфильтровано: {len(cars)} НОВЫХ машин для {filter_name}")
            logger.info(f"⏭️ Пропущено существующих: {skipped_existing}")
            logger.info(f"📊 Соотношение: {len(cars)} новых / {skipped_existing} существующих")

            return cars

        finally:
            driver.quit()

    async def scrape_cars(self, filter_name: str, existing_links: Set[str] = None) -> List[CarCreate]:
        """🎯 ОПТИМИЗИРОВАННЫЙ async метод с передачей existing_links"""
        filter_config = settings.car_filters.get(filter_name)
        if not filter_config:
            logger.warning(f"❌ Фильтр {filter_name} не найден в конфигурации")
            return []

        filter_config["filter_name"] = filter_name

        # Если existing_links не передан, создаем пустой set
        if existing_links is None:
            existing_links = set()
            logger.warning(f"⚠️ existing_links не передан для {filter_name}, парсим все объявления")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._scrape_cars_sync, filter_config, existing_links)

    # 🆕 НОВЫЕ МЕТОДЫ ДЛЯ ОТСЛЕЖИВАНИЯ ИЗМЕНЕНИЙ

    async def get_single_car_data(self, car_url: str) -> Optional[Dict[str, Any]]:
        """🎯 Получает актуальные данные по конкретной ссылке (для проверки изменений)"""
        logger.info(f"🎯 get_single_car_data() called for: {car_url[:50]}...")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_single_car_data_sync, car_url)

    def _get_single_car_data_sync(self, car_url: str) -> Optional[Dict[str, Any]]:
        """Синхронное получение данных одной машины"""
        driver = self._create_driver()
        try:
            logger.debug(f"🌐 Loading page: {car_url}")
            driver.get(car_url)

            # Ждем загрузки основного контента
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "announcement-block"))
                )
            except:
                # Если не нашли announcement-block, пробуем другие селекторы
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "page-content"))
                    )
                except:
                    logger.warning(f"⚠️ Page structure might have changed for: {car_url}")

            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            # Проверяем что страница не показывает "объявление удалено"
            if self._is_ad_removed(soup):
                logger.info(f"❌ Ad removed/unavailable: {car_url}")
                return None

            # Извлекаем цену
            price = self._extract_price_from_page(soup)

            # Извлекаем описание
            description = self._extract_description_from_page(soup)

            # Дополнительные данные для полноты
            title = self._extract_title_from_page(soup)

            result = {
                "price": price,
                "description": description,
                "title": title,
                "url": car_url,
                "last_updated": datetime.now().isoformat()
            }

            logger.debug(f"✅ Single car data extracted: price={price}, desc_len={len(description or '')}")
            return result

        except Exception as e:
            logger.error(f"❌ Error getting single car data from {car_url}: {e}")
            return None
        finally:
            driver.quit()

    def _is_ad_removed(self, soup: BeautifulSoup) -> bool:
        """Проверяет удалено ли объявление"""
        # Ищем признаки удаленного объявления
        removed_indicators = [
            "объявление удалено",
            "ad has been removed",
            "404",
            "не найдено",
            "not found",
            "page not found"
        ]

        page_text = soup.get_text().lower()
        return any(indicator in page_text for indicator in removed_indicators)

    def _extract_price_from_page(self, soup: BeautifulSoup) -> str:
        """Извлекает цену со страницы объявления"""
        # Пробуем разные селекторы для цены
        price_selectors = [
            ".announcement-price__cost",
            ".price-section .price",
            ".announcement-block .price",
            "[data-testid='price']",
            ".price-block .price",
            ".cost-primary"
        ]

        for selector in price_selectors:
            price_element = soup.select_one(selector)
            if price_element:
                price_text = price_element.get_text(strip=True)
                if price_text and any(c.isdigit() for c in price_text):
                    logger.debug(f"💰 Price found with selector '{selector}': {price_text}")
                    return price_text

        # Fallback: ищем текст содержащий € и цифры
        for element in soup.find_all(text=True):
            if '€' in element and any(c.isdigit() for c in element):
                price_text = element.strip()
                if len(price_text) < 50:  # Разумная длина для цены
                    logger.debug(f"💰 Price found via fallback: {price_text}")
                    return price_text

        logger.warning("💰 Price not found on page")
        return ""

    def _extract_description_from_page(self, soup: BeautifulSoup) -> str:
        """Извлекает описание со страницы объявления"""
        # Пробуем разные селекторы для описания
        description_selectors = [
            ".js-description",
            ".announcement-description",
            ".description-text",
            "[data-testid='description']",
            ".announcement-block .description",
            ".ad-description"
        ]

        for selector in description_selectors:
            desc_element = soup.select_one(selector)
            if desc_element:
                # Собираем текст из всех параграфов
                paragraphs = desc_element.find_all(['p', 'div', 'span'])
                if paragraphs:
                    desc_text = ' '.join(p.get_text(' ', strip=True) for p in paragraphs)
                else:
                    desc_text = desc_element.get_text(' ', strip=True)

                if desc_text and len(desc_text.strip()) > 10:
                    logger.debug(f"📝 Description found with selector '{selector}': {len(desc_text)} chars")
                    return desc_text.strip()

        logger.warning("📝 Description not found on page")
        return ""

    def _extract_title_from_page(self, soup: BeautifulSoup) -> str:
        """Извлекает заголовок объявления"""
        # Пробуем разные селекторы для заголовка
        title_selectors = [
            ".announcement-title",
            ".page-title h1",
            ".ad-title",
            "h1.title",
            "[data-testid='title']"
        ]

        for selector in title_selectors:
            title_element = soup.select_one(selector)
            if title_element:
                title_text = title_element.get_text(strip=True)
                if title_text:
                    logger.debug(f"🏷️ Title found: {title_text[:50]}")
                    return title_text

        # Fallback: title из <title> тега
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Убираем лишние части типа "| Bazaraki"
            if '|' in title_text:
                title_text = title_text.split('|')[0].strip()
            return title_text

        return ""

    async def get_available_filters(self) -> Dict[str, Dict]:
        """Возвращает доступные фильтры с информацией о режиме"""
        filters_info = {}

        for name, config in settings.car_filters.items():
            filters_info[name] = {
                "brand": config["brand"],
                "min_year": config["min_year"],
                "max_mileage": config["max_mileage"],
                "urgent_mode": config.get("urgent_mode", False),
                "price_range": self._extract_price_range(config["url"])
            }

        return filters_info

    def _extract_price_range(self, url: str) -> str:
        """Извлекает ценовой диапазон из URL"""
        try:
            price_min_match = re.search(r'price_min=(\d+)', url)
            price_max_match = re.search(r'price_max=(\d+)', url)

            if price_min_match and price_max_match:
                min_price = int(price_min_match.group(1))
                max_price = int(price_max_match.group(1))
                return f"€{min_price:,} - €{max_price:,}"
        except:
            pass
        return "неизвестно"


def _debug_page_content(self, soup: BeautifulSoup, filter_name: str):
    """🐛 Дебаг содержимого страницы"""
    logger.info(f"🐛 DEBUG {filter_name} - анализ страницы:")

    # Проверяем основные контейнеры
    all_divs = soup.find_all("div")
    logger.info(f"📄 Всего div элементов: {len(all_divs)}")

    # Ищем объявления по разным селекторам
    selectors_to_try = [
        "div.advert.js-item-listing",  # Текущий
        "div.advert",  # Упрощенный
        "div[class*='advert']",  # Любой с advert в классе
        "div[class*='item']",  # Любой с item в классе
        "div[class*='listing']",  # Любой с listing в классе
        ".announcement-item",  # Альтернативный
        ".ad-item",  # Еще альтернативный
        "[data-testid*='ad']",  # По data-testid
    ]

    for selector in selectors_to_try:
        found = soup.select(selector)
        logger.info(f"🔍 '{selector}': найдено {len(found)} элементов")

        if len(found) > 0 and len(found) <= 5:
            # Показываем структуру первых элементов
            for i, elem in enumerate(found[:2]):
                classes = elem.get('class', [])
                logger.info(f"  Элемент {i + 1}: классы={classes}")

    # Проверяем есть ли ссылки на машины
    car_links = soup.find_all("a", href=True)
    bazaraki_links = [a for a in car_links if "bazaraki.com/adv/" in a.get('href', '')]
    logger.info(f"🔗 Ссылок на объявления: {len(bazaraki_links)}")

    # Проверяем заголовок страницы
    title = soup.find("title")
    page_title = title.text if title else "Нет заголовка"
    logger.info(f"📄 Заголовок страницы: {page_title}")

    # Проверяем есть ли ошибки на странице
    error_indicators = [
        "404", "not found", "page not found",
        "error", "ошибка", "нет результатов", "no results"
    ]
    page_text = soup.get_text().lower()
    for indicator in error_indicators:
        if indicator in page_text:
            logger.warning(f"⚠️ Найден индикатор проблемы: '{indicator}'")