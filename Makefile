# ────────────────────────────────────────────
# 1) Кросс-платформенные переменные
# ────────────────────────────────────────────

# В Windows переменная OS автоматически равна Windows_NT
ifeq ($(OS),Windows_NT)
  # Будем звать python (а не python3)
  PYTHON := python

  # ISO-время для BUILD_TIME
  DATE_CMD       := powershell -NoProfile -Command "Get-Date -Format s"
  # Формат для имени файла: 20250609_153012
  DATE_FILE_CMD  := powershell -NoProfile -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"
  # Задержка в секундах
  SLEEP_CMD      := powershell -NoProfile -Command "Start-Sleep -Seconds"
else
  PYTHON         := python3
  DATE_CMD       := date -Iseconds
  DATE_FILE_CMD  := date +%Y%m%d_%H%M%S
  SLEEP_CMD      := sleep
endif

# BUILD_TIME будет вычисляться при первом обращении
BUILD_TIME ?= $(shell $(DATE_CMD))

# ────────────────────────────────────────────
# 2) Ваши обычные переменные и цели
# ────────────────────────────────────────────

PROJECT_NAME ?= car-monitor
SERVICE_NAME ?= app
PYTHON_VERSION ?= 3.11

.DEFAULT_GOAL := help

.PHONY: help
help: ## Показать список целей
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	   /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-27s\033[0m %s\n", $$1, $$2 } \
	   /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development
.PHONY: setup
setup: ## Настройка окружения
	@echo "🔧 Setting up dev..."
	@if [ ! -f .env ]; then cp .env.example .env; echo "📄 .env создан"; fi

.PHONY: install
install: ## pip install
	@echo "📦 Installing deps..."
	pip install -r requirements.txt

.PHONY: dev
dev: ## Запустить FastAPI локально
	@echo "🚀 Starting uvicorn..."
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

##@ Docker Operations
.PHONY: up
up: ## docker-compose up
	@echo "🐳 Starting containers..."
	docker-compose up -d

.PHONY: down
down: ## docker-compose down
	@echo "⏹️  Stopping containers..."
	docker-compose down --remove-orphans

.PHONY: rebuild
rebuild: ## build + up
	@echo "🔨 Rebuilding..."
	docker-compose down --remove-orphans
	docker-compose build --no-cache
	docker-compose up -d

##@ Database
.PHONY: db-reset
db-reset: ## Сброс БД (DESTRUCTIVE)
	@echo "💀 Resetting DB..."
	docker-compose down
ifeq ($(OS),Windows_NT)
	@echo "⚠️  Windows: пропускаем автоматический rm volume"
else
	-docker volume rm $(shell docker-compose config --volumes | grep mysql) 2>/dev/null
endif
	docker-compose up -d mysql
	@echo "⏳ Waiting for MySQL..."
	$(SLEEP_CMD) 10
	docker-compose up -d $(SERVICE_NAME)

.PHONY: migrate
migrate: ## alembic upgrade
	@echo "📈 Migrations..."
	docker-compose exec $(SERVICE_NAME) alembic upgrade head

##@ Logs & Monitoring
.PHONY: logs
logs: ## Все логи
	docker-compose logs -f

.PHONY: logs-app
logs-app: ## Только логи приложения
	docker-compose logs -f $(SERVICE_NAME)

##@ Misc
.PHONY: status
status: ## контейнеры + health
	@make ps
	@make check-health

.PHONY: ps
ps: ## показать контейнеры
	docker-compose ps

.PHONY: check-health
check-health: ## проверка /health
	@echo "🏥 Health check..."
	curl -s http://localhost:8000/health | $(PYTHON) -m json.tool || echo "API не отвечает"

##@ Backup
.PHONY: backup-db
backup-db: ## Бекап БД в SQL файл
	@echo "💾 Backing up DB..."
	docker-compose exec mysql mysqldump -u caruser -pcarpass car_monitor \
	  > backup_$(shell $(DATE_FILE_CMD)).sql
	@echo "✅ Saved as backup_*.sql"

##@ Sleep-helper (пример)
.PHONY: wait
wait: ## Демка SLEEP
	@echo "⏳ Ждем 5 сек..."
	$(SLEEP_CMD) 5 && echo "Поехали!" 
