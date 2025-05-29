#!/usr/bin/env python3
"""
Startup script для инициализации Alembic и запуска приложения
"""
import os
import subprocess
import sys
import time
from pathlib import Path


def wait_for_mysql():
    """Ждем готовности MySQL"""
    print("[STARTUP] Ожидание MySQL...")
    max_retries = 30
    for i in range(max_retries):
        try:
            result = subprocess.run([
                "python", "-c",
                "import aiomysql; import asyncio; asyncio.run(aiomysql.connect(host='mysql', port=3306, user='caruser', password='carpass', db='car_monitor'))"
            ], capture_output=True, timeout=5)
            if result.returncode == 0:
                print("[STARTUP] MySQL готов!")
                return True
        except Exception as e:
            print(f"[STARTUP] Ошибка: {e}")
        print(f"[STARTUP] Попытка {i + 1}/{max_retries}...")
        time.sleep(2)
    return False


def init_alembic():
    """Инициализация Alembic"""
    if not Path("alembic.ini").exists():
        print("[STARTUP] Инициализация Alembic...")
        subprocess.run(["alembic", "init", "alembic"], check=True)

        # Обновляем env.py для async
        env_content = '''import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from app.models.car import Base
from app.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''
        with open("alembic/env.py", "w") as f:
            f.write(env_content)

    # Создаем миграцию
    versions_dir = Path("alembic/versions")
    if not any(versions_dir.glob("*.py")):
        print("[STARTUP] Создание первой миграции...")
        subprocess.run(["alembic", "revision", "--autogenerate", "-m", "Initial migration"], check=True)

    print("[STARTUP] Применение миграций...")
    subprocess.run(["alembic", "upgrade", "head"], check=True)


if __name__ == "__main__":
    if not wait_for_mysql():
        print("[ERROR] MySQL недоступен")
        sys.exit(1)

    init_alembic()

    print("[STARTUP] Запуск FastAPI...")
    os.system("uvicorn app.main:app --host 0.0.0.0 --port 8000")