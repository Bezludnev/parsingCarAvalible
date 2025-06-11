# app/repository/car_repository.py - с методом для получения существующих ссылок
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text
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

    async def get_cars_for_changes_check(self, cutoff_time: datetime, limit: int = 500) -> List[Car]:
        """🔄 Получает машины которые нужно проверить на изменения"""
        logger.info(
            f"🔍 get_cars_for_changes_check() called with cutoff: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}, limit: {limit}")

        result = await self.session.execute(
            select(Car)
            .where(
                and_(
                    # Машины которые не проверялись давно или вообще не проверялись
                    or_(
                        Car.last_checked_at.is_(None),
                        Car.last_checked_at < cutoff_time
                    ),
                    # Исключаем помеченные как недоступные (можно добавить поле is_available)
                    Car.is_notified == True  # Только уже обработанные машины
                )
            )
            .order_by(
                # MySQL compatible ordering: NULL values first, then by date
                Car.last_checked_at.is_(None).desc(),
                Car.last_checked_at.asc(),
                Car.created_at.desc()
            )
            .limit(limit)
        )
        cars = result.scalars().all()

        # Детальная статистика
        never_checked = sum(1 for car in cars if car.last_checked_at is None)
        old_checked = len(cars) - never_checked

        logger.info(f"📊 get_cars_for_changes_check() found {len(cars)} cars:")
        logger.info(f"  🆕 Never checked: {never_checked}")
        logger.info(f"  ⏰ Old checked: {old_checked}")

        if cars:
            oldest_car = min((car for car in cars if car.last_checked_at),
                             key=lambda x: x.last_checked_at, default=None)
            if oldest_car and oldest_car.last_checked_at:
                logger.info(
                    f"  📅 Oldest check: {oldest_car.last_checked_at.strftime('%Y-%m-%d %H:%M:%S')} (car {oldest_car.id})")

        return cars

    async def update_last_checked(self, car_id: int):
        """📅 Обновляет время последней проверки"""
        logger.debug(f"📅 update_last_checked() for car {car_id}")

        car = await self.session.get(Car, car_id)
        if car:
            old_time = car.last_checked_at
            car.last_checked_at = datetime.now()
            await self.session.commit()

            logger.debug(f"✅ Car {car_id} last_checked updated: "
                         f"{old_time.strftime('%H:%M:%S') if old_time else 'never'} → "
                         f"{car.last_checked_at.strftime('%H:%M:%S')}")
        else:
            logger.warning(f"❌ Car {car_id} not found for last_checked update")

    async def update_price_change(self, car_id: int, old_price: str, new_price: str):
        """💰 Обновляет информацию об изменении цены"""
        logger.info(f"💰 update_price_change() for car {car_id}: '{old_price}' → '{new_price}'")

        car = await self.session.get(Car, car_id)
        if car:
            car.previous_price = old_price
            car.price = new_price
            car.price_changed_at = datetime.now()
            car.price_changes_count = (car.price_changes_count or 0) + 1
            car.last_checked_at = datetime.now()
            await self.session.commit()

            logger.info(f"✅ Price change saved for car {car_id}: "
                        f"change #{car.price_changes_count} at {car.price_changed_at.strftime('%H:%M:%S')}")
        else:
            logger.error(f"❌ Car {car_id} not found for price change update")

    async def update_description_change(self, car_id: int, old_description: str, new_description: str):
        """📝 Обновляет информацию об изменении описания"""
        logger.info(f"📝 update_description_change() for car {car_id}: "
                    f"{len(old_description or '')} chars → {len(new_description or '')} chars")

        car = await self.session.get(Car, car_id)
        if car:
            car.previous_description = old_description
            car.description = new_description
            car.description_changed_at = datetime.now()
            car.description_changes_count = (car.description_changes_count or 0) + 1
            car.last_checked_at = datetime.now()
            await self.session.commit()

            logger.info(f"✅ Description change saved for car {car_id}: "
                        f"change #{car.description_changes_count} at {car.description_changed_at.strftime('%H:%M:%S')}")
        else:
            logger.error(f"❌ Car {car_id} not found for description change update")

    async def mark_as_unavailable(self, car_id: int):
        """❌ Помечает машину как недоступную (продана/удалена)"""
        logger.warning(f"❌ mark_as_unavailable() for car {car_id}")

        # Можно добавить поле is_available в модель, пока просто обновим время проверки
        car = await self.session.get(Car, car_id)
        if car:
            car.last_checked_at = datetime.now()
            # Можно добавить поле car.is_available = False
            await self.session.commit()

            logger.warning(f"🚫 Car {car_id} marked as unavailable: {car.title[:50]}")
        else:
            logger.error(f"❌ Car {car_id} not found for unavailable marking")

    async def get_recent_price_changes(self, days: int = 7) -> List[Car]:
        """💰 Получает машины с недавними изменениями цены"""
        cutoff_date = datetime.now() - timedelta(days=days)
        result = await self.session.execute(
            select(Car)
            .where(
                and_(
                    Car.price_changed_at >= cutoff_date,
                    Car.price_changed_at.isnot(None)
                )
            )
            .order_by(Car.price_changed_at.desc())
        )
        return result.scalars().all()

    async def get_recent_description_changes(self, days: int = 7) -> List[Car]:
        """📝 Получает машины с недавними изменениями описания"""
        cutoff_date = datetime.now() - timedelta(days=days)
        result = await self.session.execute(
            select(Car)
            .where(
                and_(
                    Car.description_changed_at >= cutoff_date,
                    Car.description_changed_at.isnot(None)
                )
            )
            .order_by(Car.description_changed_at.desc())
        )
        return result.scalars().all()

    async def get_changes_summary(self, days: int = 7) -> Dict[str, Any]:
        """📊 Сводка изменений за период"""
        cutoff_date = datetime.now() - timedelta(days=days)

        # Изменения цен
        price_changes_result = await self.session.execute(
            select(func.count(Car.id))
            .where(
                and_(
                    Car.price_changed_at >= cutoff_date,
                    Car.price_changed_at.isnot(None)
                )
            )
        )
        price_changes_count = price_changes_result.scalar()

        # Изменения описаний
        desc_changes_result = await self.session.execute(
            select(func.count(Car.id))
            .where(
                and_(
                    Car.description_changed_at >= cutoff_date,
                    Car.description_changed_at.isnot(None)
                )
            )
        )
        desc_changes_count = desc_changes_result.scalar()

        # Общее количество проверок
        checks_result = await self.session.execute(
            select(func.count(Car.id))
            .where(
                and_(
                    Car.last_checked_at >= cutoff_date,
                    Car.last_checked_at.isnot(None)
                )
            )
        )
        total_checks = checks_result.scalar()

        # Топ машин с наибольшим количеством изменений цены
        top_price_changers_result = await self.session.execute(
            select(Car)
            .where(Car.price_changes_count > 0)
            .order_by(Car.price_changes_count.desc())
            .limit(5)
        )
        top_price_changers = top_price_changers_result.scalars().all()

        return {
            "period_days": days,
            "price_changes_count": price_changes_count,
            "description_changes_count": desc_changes_count,
            "total_checks": total_checks,
            "top_price_changers": [
                {
                    "id": car.id,
                    "title": car.title,
                    "price_changes": car.price_changes_count,
                    "current_price": car.price,
                    "previous_price": car.previous_price
                }
                for car in top_price_changers
            ]
        }

    async def get_cars_never_checked(self, limit: int = 100) -> List[Car]:
        """🔍 Получает машины которые ни разу не проверялись на изменения"""
        result = await self.session.execute(
            select(Car)
            .where(
                and_(
                    Car.last_checked_at.is_(None),
                    Car.is_notified == True  # Только уже обработанные
                )
            )
            .order_by(Car.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_cars_with_price_drops(self, days: int = 7, min_drop_euros: int = 500) -> List[Car]:
        """💸 Получает машины со значительным падением цены"""
        cutoff_date = datetime.now() - timedelta(days=days)

        # Получаем машины с недавними изменениями цены
        cars_with_changes = await self.get_recent_price_changes(days)

        significant_drops = []
        for car in cars_with_changes:
            if car.previous_price and car.price:
                try:
                    # Извлекаем числовые значения цен
                    old_price_num = self._extract_price_number(car.previous_price)
                    new_price_num = self._extract_price_number(car.price)

                    if old_price_num and new_price_num:
                        price_drop = old_price_num - new_price_num
                        if price_drop >= min_drop_euros:
                            significant_drops.append(car)
                except:
                    continue

        return significant_drops

    def _extract_price_number(self, price_text: str) -> Optional[int]:
        """Извлекает число из текста цены"""
        import re
        if not price_text:
            return None

        # Убираем все кроме цифр
        numbers = re.findall(r'\d+', price_text.replace(',', '').replace(' ', ''))
        if numbers:
            try:
                return int(''.join(numbers))
            except:
                return None
        return None