from pydantic_settings import BaseSettings
from typing import List, Dict


class Settings(BaseSettings):
    database_url: str
    telegram_bot_token: str
    telegram_chat_id: str
    chromedriver_path: str = "/usr/local/bin/chromedriver"

    # Фильтры для поиска
    car_filters: Dict[str, Dict] = {
        "mercedes": {
            "url": "https://www.bazaraki.com/car-motorbikes-boats-and-parts/cars-trucks-and-vans/mercedes/?price_min=6000&price_max=12500",
            "min_year": 2012,
            "max_mileage": 200000,
            "brand": "Mercedes"
        },
        "bmw": {
            "url": "https://www.bazaraki.com/car-motorbikes-boats-and-parts/cars-trucks-and-vans/bmw/mileage_max---125000/?price_min=6000&price_max=12500",
            "min_year": 2012,
            "max_mileage": 125000,
            "brand": "BMW"
        },
        "audi": {
            "url": "https://www.bazaraki.com/car-motorbikes-boats-and-parts/cars-trucks-and-vans/audi/year_min---63/?price_min=6000&price_max=12500",
            "min_year": 2012,
            "max_mileage": 125000,
            "brand": "Audi"
        }
    }

    class Config:
        env_file = ".env"


settings = Settings()
