import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# Импортируй свой Base и settings (путь может отличаться! поправь под свой проект)
from app.models.car import Base  # или from app.models import Base
from app.config import settings  # settings должен содержать .database_url

# Alembic Config object, предоставленный из alembic.ini
config = context.config

# Устанавливаем URL БД из конфига/настроек
config.set_main_option("sqlalchemy.url", settings.database_url)

# Интерпретируем конфиг-файл для логирования, если он указан
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные моделей для автогенерации миграций
target_metadata = Base.metadata

def run_migrations_offline():
    """Запуск миграций в оффлайн-режиме (генерирует SQL скрипты)"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    """Запуск миграций в async-режиме"""
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    """Асинхронный онлайн-режим"""
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
