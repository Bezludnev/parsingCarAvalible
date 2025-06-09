from pydantic_settings import BaseSettings
from typing import List, Dict


class Settings(BaseSettings):
    database_url: str
    telegram_bot_token: str
    telegram_chat_id: str
    chromedriver_path: str = "/usr/local/bin/chromedriver"
    openai_api_key: str

    # Основные фильтры для поиска
    car_filters: Dict[str, Dict] = {
        "mercedes": {
            "url": "https://www.bazaraki.com/car-motorbikes-boats-and-parts/cars-trucks-and-vans/mercedes/?price_min=6000&price_max=15000",
            "min_year": 2012,
            "max_mileage": 200000,
            "brand": "Mercedes"
        },
        "bmw": {
            "url": "https://www.bazaraki.com/car-motorbikes-boats-and-parts/cars-trucks-and-vans/bmw/mileage_max---125000/?price_min=6000&price_max=15000",
            "min_year": 2012,
            "max_mileage": 125000,
            "brand": "BMW"
        },
        "audi": {
            "url": "https://www.bazaraki.com/car-motorbikes-boats-and-parts/cars-trucks-and-vans/audi/year_min---63/?price_min=6000&price_max=15000",
            "min_year": 2012,
            "max_mileage": 125000,
            "brand": "Audi"
        },

        # 🔥 URGENT фильтры - расширенная выборка для срочной продажи
        "mercedes_urgent": {
            "url": "https://www.bazaraki.com/car-motorbikes-boats-and-parts/cars-trucks-and-vans/mercedes/?price_min=4000&price_max=15000",
            "min_year": 2008,  # Снизили с 2012
            "max_mileage": 350000,  # Увеличили
            "brand": "Mercedes",
            "urgent_mode": True
        },
        "bmw_urgent": {
            "url": "https://www.bazaraki.com/car-motorbikes-boats-and-parts/cars-trucks-and-vans/bmw/?price_min=4000&price_max=15000",
            "min_year": 2008,
            "max_mileage": 300000,  # Увеличили с 125k
            "brand": "BMW",
            "urgent_mode": True
        },
        "audi_urgent": {
            "url": "https://www.bazaraki.com/car-motorbikes-boats-and-parts/cars-trucks-and-vans/audi/?price_min=4000&price_max=15000",
            "min_year": 2008,
            "max_mileage": 300000,
            "brand": "Audi",
            "urgent_mode": True
        },
        # 🎯 BUDGET срочная продажа - дешевые варианты
        "budget_urgent": {
            "url": "https://www.bazaraki.com/car-motorbikes-boats-and-parts/cars-trucks-and-vans/mercedes/slk-class/?price_min=6000&price_max=8000",
            "min_year": 2005,
            "max_mileage": 400000,
            "brand": "Budget",
            "urgent_mode": True
        }
    }

    class Config:
        env_file = ".env"


settings = Settings()