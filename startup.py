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


def clean_alembic_state():
    """Очищает состояние alembic в базе данных"""
    print("[STARTUP] Очистка состояния Alembic в базе...")
    try:
        clean_script = """
import aiomysql
import asyncio

async def clean_db():
    conn = await aiomysql.connect(
        host='mysql', port=3306, 
        user='caruser', password='carpass', 
        db='car_monitor'
    )
    async with conn.cursor() as cursor:
        # Удаляем таблицу alembic_version если существует
        await cursor.execute("DROP TABLE IF EXISTS alembic_version")
        # Удаляем таблицу cars если существует
        await cursor.execute("DROP TABLE IF EXISTS cars")
        await conn.commit()
        print("База данных очищена")
    conn.close()

asyncio.run(clean_db())
"""
        result = subprocess.run([
            "python", "-c", clean_script
        ], capture_output=True, timeout=10, text=True)

        if result.returncode == 0:
            print("[STARTUP] ✅ База данных очищена")
            return True
        else:
            print(f"[STARTUP] ⚠️ Ошибка очистки: {result.stderr}")
            return False

    except Exception as e:
        print(f"[STARTUP] ⚠️ Не удалось очистить базу: {e}")
        return False


def init_alembic():
    """Инициализация Alembic"""
    if not Path("alembic.ini").exists():
        print("[STARTUP] Инициализация Alembic...")
        subprocess.run(["alembic", "init", "alembic"], check=True)

        # Обновляем alembic.ini для MySQL
        with open("alembic.ini", "r") as f:
            ini_content = f.read()

        # Заменяем sqlalchemy.url на переменную окружения
        ini_content = ini_content.replace(
            "sqlalchemy.url = driver://user:pass@localhost/dbname",
            "# sqlalchemy.url = driver://user:pass@localhost/dbname\n# URL устанавливается в env.py"
        )

        with open("alembic.ini", "w") as f:
            f.write(ini_content)

        # Обновляем env.py для async
        env_content = '''import asyncio
import os
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# this is the Alembic Config object
config = context.config

# Получаем URL из переменной окружения
database_url = os.getenv('DATABASE_URL', 'mysql+aiomysql://caruser:carpass@mysql:3306/car_monitor')
config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Импортируем модели
try:
    from app.models.car import Base
    target_metadata = Base.metadata
except ImportError as e:
    print(f"Warning: Could not import models: {e}")
    target_metadata = None

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
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
    """In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        echo=True  # Для отладки
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''
        with open("alembic/env.py", "w") as f:
            f.write(env_content)

    # Проверяем есть ли уже миграции
    versions_dir = Path("alembic/versions")
    if not versions_dir.exists():
        versions_dir.mkdir(exist_ok=True)

    # Проверяем есть ли файлы миграций
    migration_files = list(versions_dir.glob("*.py"))
    if not migration_files:
        print("[STARTUP] Создание первой миграции...")

        # Сначала попробуем создать пустую миграцию
        try:
            subprocess.run([
                "alembic", "revision",
                "--autogenerate",
                "-m", "Initial migration"
            ], check=True, capture_output=True, text=True)
            print("[STARTUP] ✅ Автогенерированная миграция создана")
        except subprocess.CalledProcessError as e:
            print(f"[STARTUP] ⚠️ Автогенерация не удалась: {e}")
            print("[STARTUP] Создаем базовую миграцию вручную...")

            # Создаем миграцию вручную
            result = subprocess.run([
                "alembic", "revision",
                "-m", "Initial migration"
            ], check=True, capture_output=True, text=True)

            # Находим созданный файл миграции
            migration_files = list(versions_dir.glob("*.py"))
            if migration_files:
                migration_file = migration_files[-1]  # Последний созданный

                # Заполняем миграцию содержимым
                migration_content = f'''"""Initial migration

Revision ID: {migration_file.stem.split('_')[0]}
Revises: 
Create Date: {time.strftime('%Y-%m-%d %H:%M:%S')}

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers
revision = '{migration_file.stem.split('_')[0]}'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('cars',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('link', sa.String(length=500), nullable=False),
        sa.Column('price', sa.String(length=100), nullable=True),
        sa.Column('brand', sa.String(length=50), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('mileage', sa.Integer(), nullable=True),
        sa.Column('features', sa.Text(), nullable=True),
        sa.Column('date_posted', sa.String(length=100), nullable=True),
        sa.Column('place', sa.String(length=200), nullable=True),
        sa.Column('filter_name', sa.String(length=50), nullable=True),
        sa.Column('is_notified', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cars_brand'), 'cars', ['brand'], unique=False)
    op.create_index(op.f('ix_cars_filter_name'), 'cars', ['filter_name'], unique=False)
    op.create_index(op.f('ix_cars_id'), 'cars', ['id'], unique=False)
    op.create_index(op.f('ix_cars_link'), 'cars', ['link'], unique=True)
    op.create_index(op.f('ix_cars_mileage'), 'cars', ['mileage'], unique=False)
    op.create_index(op.f('ix_cars_year'), 'cars', ['year'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_cars_year'), table_name='cars')
    op.drop_index(op.f('ix_cars_mileage'), table_name='cars')
    op.drop_index(op.f('ix_cars_link'), table_name='cars')
    op.drop_index(op.f('ix_cars_id'), table_name='cars')
    op.drop_index(op.f('ix_cars_filter_name'), table_name='cars')
    op.drop_index(op.f('ix_cars_brand'), table_name='cars')
    op.drop_table('cars')
    # ### end Alembic commands ###
'''

                with open(migration_file, "w") as f:
                    f.write(migration_content)

                print(f"[STARTUP] ✅ Создана базовая миграция: {migration_file.name}")

    print("[STARTUP] Применение миграций...")
    try:
        result = subprocess.run(["alembic", "upgrade", "head"],
                                check=True, capture_output=True, text=True)
        print("[STARTUP] ✅ Миграции применены успешно")
    except subprocess.CalledProcessError as e:
        print(f"[STARTUP] ❌ Ошибка применения миграций:")
        print(f"Return code: {e.returncode}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")

        # Попробуем показать текущее состояние alembic
        try:
            current_result = subprocess.run(["alembic", "current"],
                                            capture_output=True, text=True)
            print(f"Alembic current: {current_result.stdout}")
        except:
            pass

        raise


if __name__ == "__main__":
    if not wait_for_mysql():
        print("[ERROR] MySQL недоступен")
        sys.exit(1)

    # Очищаем состояние базы данных
    clean_alembic_state()

    try:
        init_alembic()
        print("[STARTUP] ✅ База данных инициализирована")
    except Exception as e:
        print(f"[ERROR] Ошибка инициализации базы: {e}")
        sys.exit(1)

    print("[STARTUP] Запуск FastAPI...")
    os.system("uvicorn app.main:app --host 0.0.0.0 --port 8000")