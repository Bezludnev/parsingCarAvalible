# app/repository/car_repository.py - с методом для получения существующих ссылок
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func, text
from app.models.car import Car
from app.schemas.car import CarCreate
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timedelta


class CarRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_link(self, link: str) -> Optional[Car]:
        result = await self.session.execute(
            select(Car).where(Car.link == link)
        )
        return result.scalar_one_or_none()

    async def get_existing_links_by_filter(self, filter_name: str) -> Set[str]:
        """🎯 НОВЫЙ: Получает все существующие ссылки для фильтра"""
        result = await self.session.execute(
            select(Car.link).where(Car.filter_name == filter_name)
        )
        links = result.scalars().all()
        return set(links)

    async def get_all_existing_links(self) -> Set[str]:
        """Получает все существующие ссылки из базы"""
        result = await self.session.execute(
            select(Car.link)
        )
        links = result.scalars().all()
        return set(links)

    async def create(self, car_data: CarCreate) -> Car:
        car = Car(**car_data.dict())
        self.session.add(car)
        await self.session.commit()
        await self.session.refresh(car)
        return car

    async def get_unnotified_cars(self) -> List[Car]:
        result = await self.session.execute(
            select(Car).where(Car.is_notified == False)
        )
        return result.scalars().all()

    async def mark_as_notified(self, car_id: int):
        car = await self.session.get(Car, car_id)
        if car:
            car.is_notified = True
            await self.session.commit()

    async def get_cars_by_filter(self, filter_name: str, limit: int = 10) -> List[Car]:
        result = await self.session.execute(
            select(Car)
            .where(Car.filter_name == filter_name)
            .order_by(Car.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_recent_cars(self, days: int = 7, limit: int = 30) -> List[Car]:
        """Получает машины за последние N дней"""
        cutoff_date = datetime.now() - timedelta(days=days)
        result = await self.session.execute(
            select(Car)
            .where(Car.created_at >= cutoff_date)
            .order_by(Car.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_cars_by_ids(self, car_ids: List[int]) -> List[Car]:
        """Получает машины по списку ID"""
        result = await self.session.execute(
            select(Car).where(Car.id.in_(car_ids))
        )
        return result.scalars().all()

    async def get_cars_by_brand(self, brand: str, limit: int = 15) -> List[Car]:
        """Получает машины по марке"""
        result = await self.session.execute(
            select(Car)
            .where(Car.brand.ilike(f"%{brand}%"))
            .order_by(Car.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    # 🎯 МЕТОДЫ ДЛЯ АНАЛИЗА ВСЕЙ БАЗЫ

    async def get_all_cars_for_analysis(self, limit: int = 1000) -> List[Car]:
        """🎯 Получает ВСЕ машины из базы для анализа"""
        result = await self.session.execute(
            select(Car)
            .order_by(Car.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_global_statistics(self) -> Dict[str, Any]:
        """📊 Глобальная статистика по всей базе"""
        result = await self.session.execute(
            select(
                func.count(Car.id).label('total_cars'),
                func.avg(Car.year).label('avg_year'),
                func.avg(Car.mileage).label('avg_mileage'),
                func.min(Car.year).label('min_year'),
                func.max(Car.year).label('max_year'),
                func.min(Car.mileage).label('min_mileage'),
                func.max(Car.mileage).label('max_mileage')
            )
        )
        stats = result.first()

        # Статистика по ценам
        price_stats = await self.session.execute(
            text("""
                SELECT 
                    COUNT(*) as cars_with_price,
                    AVG(CAST(REGEXP_REPLACE(REPLACE(price, '€', ''), '[^0-9]', '') AS UNSIGNED)) as avg_price,
                    MIN(CAST(REGEXP_REPLACE(REPLACE(price, '€', ''), '[^0-9]', '') AS UNSIGNED)) as min_price,
                    MAX(CAST(REGEXP_REPLACE(REPLACE(price, '€', ''), '[^0-9]', '') AS UNSIGNED)) as max_price
                FROM cars 
                WHERE price IS NOT NULL 
                AND price != '' 
                AND price REGEXP '[0-9]'
            """)
        )
        price_data = price_stats.first()

        return {
            'total_cars': stats.total_cars or 0,
            'avg_year': round(stats.avg_year, 1) if stats.avg_year else None,
            'avg_mileage': round(stats.avg_mileage, 0) if stats.avg_mileage else None,
            'min_year': stats.min_year,
            'max_year': stats.max_year,
            'min_mileage': stats.min_mileage,
            'max_mileage': stats.max_mileage,
            'cars_with_price': price_data.cars_with_price if price_data else 0,
            'avg_price': round(price_data.avg_price, 0) if price_data and price_data.avg_price else None,
            'min_price': price_data.min_price if price_data else None,
            'max_price': price_data.max_price if price_data else None
        }

    async def get_recent_statistics(self, days: int = 7) -> Dict[str, Any]:
        """📈 Статистика за последние дни"""
        cutoff_date = datetime.now() - timedelta(days=days)

        result = await self.session.execute(
            select(
                func.count(Car.id).label('new_cars_count'),
                func.avg(Car.year).label('avg_year'),
                func.avg(Car.mileage).label('avg_mileage')
            )
            .where(Car.created_at >= cutoff_date)
        )
        stats = result.first()

        return {
            'new_cars_count': stats.new_cars_count or 0,
            'avg_year': round(stats.avg_year, 1) if stats.avg_year else None,
            'avg_mileage': round(stats.avg_mileage, 0) if stats.avg_mileage else None,
            'period_days': days
        }

    async def get_brands_breakdown(self) -> Dict[str, int]:
        """🏷️ Разбивка по брендам"""
        result = await self.session.execute(
            select(Car.brand, func.count(Car.id).label('count'))
            .where(Car.brand.isnot(None))
            .group_by(Car.brand)
            .order_by(func.count(Car.id).desc())
        )

        return {row.brand: row.count for row in result.all()}

    async def get_filters_breakdown(self) -> Dict[str, int]:
        """📁 Разбивка по фильтрам"""
        result = await self.session.execute(
            select(Car.filter_name, func.count(Car.id).label('count'))
            .where(Car.filter_name.isnot(None))
            .group_by(Car.filter_name)
            .order_by(func.count(Car.id).desc())
        )

        return {row.filter_name: row.count for row in result.all()}

    async def get_price_ranges_analysis(self) -> Dict[str, Any]:
        """💰 Анализ ценовых диапазонов"""
        result = await self.session.execute(
            text("""
                SELECT 
                    CASE 
                        WHEN CAST(REGEXP_REPLACE(REPLACE(price, '€', ''), '[^0-9]', '') AS UNSIGNED) < 5000 THEN 'under_5k'
                        WHEN CAST(REGEXP_REPLACE(REPLACE(price, '€', ''), '[^0-9]', '') AS UNSIGNED) BETWEEN 5000 AND 10000 THEN '5k_10k'
                        WHEN CAST(REGEXP_REPLACE(REPLACE(price, '€', ''), '[^0-9]', '') AS UNSIGNED) BETWEEN 10000 AND 15000 THEN '10k_15k'
                        WHEN CAST(REGEXP_REPLACE(REPLACE(price, '€', ''), '[^0-9]', '') AS UNSIGNED) BETWEEN 15000 AND 25000 THEN '15k_25k'
                        ELSE 'over_25k'
                    END as price_range,
                    COUNT(*) as count
                FROM cars 
                WHERE price IS NOT NULL 
                AND price != '' 
                AND price REGEXP '[0-9]'
                GROUP BY price_range
                ORDER BY 
                    CASE price_range
                        WHEN 'under_5k' THEN 1
                        WHEN '5k_10k' THEN 2
                        WHEN '10k_15k' THEN 3
                        WHEN '15k_25k' THEN 4
                        WHEN 'over_25k' THEN 5
                    END
            """)
        )

        return {row.price_range: row.count for row in result.all()}

    async def get_year_distribution(self) -> Dict[int, int]:
        """📅 Распределение по годам выпуска"""
        result = await self.session.execute(
            select(Car.year, func.count(Car.id).label('count'))
            .where(Car.year.isnot(None))
            .where(Car.year > 2000)
            .group_by(Car.year)
            .order_by(Car.year.desc())
        )

        return {row.year: row.count for row in result.all()}

    async def get_market_activity_by_days(self, days: int = 30) -> Dict[str, int]:
        """📈 Активность рынка по дням"""
        cutoff_date = datetime.now() - timedelta(days=days)

        result = await self.session.execute(
            select(
                func.date(Car.created_at).label('date'),
                func.count(Car.id).label('count')
            )
            .where(Car.created_at >= cutoff_date)
            .group_by(func.date(Car.created_at))
            .order_by(func.date(Car.created_at).desc())
        )

        return {str(row.date): row.count for row in result.all()}

    # LEGACY методы (сохраняем для обратной совместимости)
    async def get_price_statistics(self, filter_name: str = None) -> Dict[str, Any]:
        """Статистика по ценам (legacy)"""
        query = select(
            func.count(Car.id).label('total'),
            func.avg(Car.year).label('avg_year'),
            func.avg(Car.mileage).label('avg_mileage')
        )

        if filter_name:
            query = query.where(Car.filter_name == filter_name)

        result = await self.session.execute(query)
        stats = result.first()

        return {
            'total_cars': stats.total,
            'avg_year': round(stats.avg_year, 1) if stats.avg_year else None,
            'avg_mileage': round(stats.avg_mileage, 1) if stats.avg_mileage else None
        }