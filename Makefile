# 1) Cross-platform settings
ifeq ($(OS), Windows_NT)
# Use native PowerShell
SHELL         := C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
.SHELLFLAGS   := -NoProfile -NoLogo -NonInteractive -ExecutionPolicy Bypass -Command
.ONESHELL:

# Utilities and commands
PYTHON         := python
DATE_CMD       := chcp.com 65001 > $null; Get-Date -Format s
DATE_FILE_CMD  := chcp.com 65001 > $null; Get-Date -Format 'yyyyMMdd_HHmmss'
SLEEP_CMD      := Start-Sleep -Seconds
CURL_CMD       := curl.exe -s
else
SHELL          := /bin/sh
PYTHON         := python3
DATE_CMD       := date -Iseconds
DATE_FILE_CMD  := date +%Y%m%d_%H%M%S
SLEEP_CMD      := sleep
CURL_CMD       := curl -s
endif

# BUILD_TIME is computed on first use
BUILD_TIME ?= $(shell $(DATE_CMD))

.DEFAULT_GOAL := help

# 2) Project settings
PROJECT_NAME   ?= car-monitor
SERVICE_NAME   ?= app
PYTHON_VERSION ?= 3.11

# 3) Help
.PHONY: help
help: ## Show available targets
ifeq ($(OS), Windows_NT)
	@powershell.exe -NoProfile -NoLogo -NonInteractive -ExecutionPolicy Bypass -Command ^
	"Write-Host 'Usage: make <target>'; " ^
	"Get-Content '$(MAKEFILE_LIST)' |" ^
	"  Select-String '^[a-zA-Z0-9_-]+:.*##' |" ^
	"  ForEach-Object { " ^
	"    $p = $_.Line -split '##'; " ^
	"    $n = ($p[0] -replace ':.*','').Trim(); " ^
	"    $d = ($p[1]).Trim(); " ^
	"    Write-Host ('  ' + $n.PadRight(27) + ' ' + $d); " ^
	"  }"
else
	@printf "\nUsage: make <target>\n\n"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ { printf "  %-27s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
endif

## Development
.PHONY: setup
setup: ## Setup environment and install dependencies
ifeq ($(OS), Windows_NT)
	@powershell.exe -NoProfile -NoLogo -NonInteractive -Command ^
	"if (!(Test-Path '.env')) { Copy-Item .env.example .env; Write-Host '📄 Created .env from example'; } " ^
	"Write-Host '✅ Setup complete! Edit .env with your tokens'"
else
	@echo "🔧 Setting up development environment..."
	@if [ ! -f .env ]; then cp .env.example .env; echo "📄 Created .env from example"; fi
	@echo "✅ Setup complete! Edit .env with your tokens"
endif

.PHONY: install
install: ## Install Python dependencies locally
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

.PHONY: dev
dev: ## Run FastAPI locally (without Docker)
	@echo "🚀 Starting FastAPI development server..."
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

## Docker Operations
.PHONY: up
up: ## Start all containers
	@echo "🐳 Starting containers..."
	docker-compose up -d

.PHONY: start
start: up ## Alias for up

.PHONY: down
down: ## Stop containers but keep volumes
	@echo "⏹️  Stopping containers..."
	docker-compose down --remove-orphans

.PHONY: stop
stop: down ## Alias for down

.PHONY: restart
restart: ## Quick restart (preserve volumes and cache)
	@echo "🔄 Quick restart..."
	docker-compose restart $(SERVICE_NAME)

.PHONY: rebuild
rebuild: ## Full rebuild and restart
	@echo "🔨 Rebuilding containers..."
	docker-compose down --remove-orphans
	docker-compose build --no-cache
	docker-compose up -d

.PHONY: watch
watch: ## Live reload mode (rebuild on changes)
	@echo "👀 Starting live reload mode..."
	docker-compose down --remove-orphans
	docker-compose up --build

.PHONY: clear
clear: ## Remove containers and volumes (DESTRUCTIVE)
	@echo "🗑️  Removing containers and volumes..."
	docker-compose down --remove-orphans --volumes
	docker system prune -f

## Database
.PHONY: db-shell
db-shell: ## Connect to MySQL shell
	docker-compose exec mysql mysql -u caruser -pcarpass car_monitor

.PHONY: db-reset
db-reset: ## Reset database (DESTRUCTIVE)
	@echo "💀 Resetting database..."
	docker-compose down
ifeq ($(OS), Windows_NT)
	@echo "⚠️  Windows: skipping volume removal"
else
	-docker volume rm $(shell docker-compose config --volumes | grep mysql) 2>/dev/null
endif
	docker-compose up -d mysql
	@echo "⏳ Waiting for MySQL..."
	$(SLEEP_CMD) 10
	docker-compose up -d $(SERVICE_NAME)

.PHONY: migrate
migrate: ## Apply Alembic migrations
	@echo "📈 Updating database migrations..."
	docker-compose exec $(SERVICE_NAME) alembic upgrade head

## Monitoring & Logs
.PHONY: logs
logs: ## Show all logs
	docker-compose logs -f

.PHONY: logs-app
logs-app: ## Show app logs only
	docker-compose logs -f $(SERVICE_NAME)

.PHONY: ps
ps: ## Show running containers
	docker-compose ps

## API Testing
.PHONY: check-health
check-health: ## Check API health
	@echo "🏥 Checking API health..."
	@$(CURL_CMD) http://localhost:8000/health | $(PYTHON) -m json.tool || echo "API not responding"

.PHONY: trigger-scraping
trigger-scraping: ## Manual trigger car scraping
	@echo "🔍 Triggering manual scraping..."
	@$(CURL_CMD) -X POST http://localhost:8000/cars/check-now | $(PYTHON) -m json.tool

## AI Analysis (NEW)
.PHONY: scheduled-analysis
scheduled-analysis: ## Run scheduled AI analysis
	@echo "🤖 Running scheduled AI analysis..."
	@$(CURL_CMD) -X POST http://localhost:8000/analysis/scheduled-analysis | $(PYTHON) -m json.tool

.PHONY: check-scheduler
check-scheduler: ## Check scheduler status
	@echo "⏰ Checking scheduler status..."
	@$(CURL_CMD) http://localhost:8000/analysis/scheduler-status | $(PYTHON) -m json.tool

.PHONY: full-market-analysis
full-market-analysis: ## Run full market analysis
	@echo "📊 Running full market analysis..."
	@$(CURL_CMD) -X POST http://localhost:8000/analysis/full-market | $(PYTHON) -m json.tool

.PHONY: database-stats
database-stats: ## Get database statistics
	@echo "📊 Getting database statistics..."
	@$(CURL_CMD) http://localhost:8000/analysis/database-stats | $(PYTHON) -m json.tool

.PHONY: market-trends
market-trends: ## Analyze market trends
	@echo "📈 Analyzing market trends..."
	@$(CURL_CMD) -X POST "http://localhost:8000/analysis/market-trends?days=14" | $(PYTHON) -m json.tool

.PHONY: ai-status
ai-status: ## Check AI service status
	@echo "🤖 Checking AI service status..."
	@$(CURL_CMD) http://localhost:8000/analysis/status | $(PYTHON) -m json.tool

## Reports Management
.PHONY: list-reports
list-reports: ## List HTML reports
	@echo "📋 Listing HTML reports..."
	@$(CURL_CMD) http://localhost:8000/reports/list | $(PYTHON) -m json.tool

.PHONY: reports-stats
reports-stats: ## Get reports statistics
	@echo "📊 Getting reports statistics..."


##@ Changes Tracking with Detailed Logs (NEW)
.PHONY: check-changes-verbose
check-changes-verbose: ## Запустить проверку изменений с подробными логами
	@echo "🔄 Checking all cars for changes (verbose logs)..."
	curl -X POST http://localhost:8000/changes/check-all | python3 -m json.tool &
	@echo "📋 Watching logs for detailed output..."
	docker-compose logs -f --tail=50 app

.PHONY: test-single-car-change
test-single-car-change: ## Проверить изменения одной машины (нужен CAR_ID)
	@echo "🔍 Testing single car change detection..."
	@if [ -z "$(CAR_ID)" ]; then \
		echo "❌ Usage: make test-single-car-change CAR_ID=123"; \
	else \
		echo "🎯 Checking car ID: $(CAR_ID)"; \
		curl -X POST "http://localhost:8000/changes/check-cars" \
			-H "Content-Type: application/json" \
			-d '[$(CAR_ID)]' | python3 -m json.tool & \
		echo "📋 Watching logs..."; \
		docker-compose logs -f --tail=20 app; \
	fi

.PHONY: logs-changes
logs-changes: ## Показать логи связанные с отслеживанием изменений
	@echo "📋 Filtering logs for changes tracking..."
	docker-compose logs app | grep -E "(check.*changes|_check_single_car|get_single_car_data|update_.*_change|send_car_changes)" | tail -30

.PHONY: logs-changes-live
logs-changes-live: ## Живые логи отслеживания изменений
	@echo "📋 Live logs for changes tracking..."
	docker-compose logs -f app | grep --line-buffered -E "(check.*changes|_check_single_car|get_single_car_data|update_.*_change|send_car_changes|scraper.*single)"
.PHONY: check-changes
check-changes: ## Запустить проверку изменений всех машин
	@echo "🔄 Checking all cars for changes..."
	curl -X POST http://localhost:8000/changes/check-all | python3 -m json.tool

.PHONY: check-specific-changes
check-specific-changes: ## Проверить изменения конкретных машин (нужен CAR_IDS)
	@echo "🎯 Checking specific cars for changes..."
	@if [ -z "$(CAR_IDS)" ]; then \
		echo "❌ Usage: make check-specific-changes CAR_IDS='[123,456,789]'"; \
	else \
		curl -X POST "http://localhost:8000/changes/check-cars" \
			-H "Content-Type: application/json" \
			-d '$(CAR_IDS)' | python3 -m json.tool; \
	fi

.PHONY: changes-summary
changes-summary: ## Сводка изменений за 7 дней
	@echo "📊 Getting changes summary..."
	curl -s "http://localhost:8000/changes/summary?days=7" | python3 -m json.tool

.PHONY: recent-price-changes
recent-price-changes: ## Показать недавние изменения цен
	@echo "💰 Getting recent price changes..."
	curl -s "http://localhost:8000/changes/recent-price-changes?days=7" | python3 -m json.tool

.PHONY: recent-description-changes
recent-description-changes: ## Показать недавние изменения описаний
	@echo "📝 Getting recent description changes..."
	curl -s "http://localhost:8000/changes/recent-description-changes?days=7" | python3 -m json.tool

.PHONY: price-drops
price-drops: ## Показать значительные падения цен (500€+)
	@echo "💸 Getting significant price drops..."
	curl -s "http://localhost:8000/changes/price-drops?days=7&min_drop_euros=500" | python3 -m json.tool

.PHONY: price-drops-big
price-drops-big: ## Показать крупные падения цен (1000€+)
	@echo "💸💸 Getting big price drops..."
	curl -s "http://localhost:8000/changes/price-drops?days=7&min_drop_euros=1000" | python3 -m json.tool

.PHONY: price-drops-alert
price-drops-alert: ## Отправить уведомление о падениях цен в Telegram
	@echo "📱 Sending price drops alert to Telegram..."
	curl -X POST "http://localhost:8000/changes/price-drops-alert?days=7&min_drop_euros=1000" | python3 -m json.tool

.PHONY: never-checked
never-checked: ## Показать машины которые ни разу не проверялись
	@echo "🔍 Getting never checked cars..."
	curl -s "http://localhost:8000/changes/never-checked?limit=20" | python3 -m json.tool

.PHONY: changes-status
changes-status: ## Статус системы отслеживания изменений
	@echo "📊 Getting changes tracking status..."
	curl -s http://localhost:8000/changes/status | python3 -m json.tool

##@ Database Migration for Changes
.PHONY: migrate-changes
migrate-changes: ## Применить миграцию для отслеживания изменений
	@echo "📈 Applying changes tracking migration..."
	docker-compose exec $(SERVICE_NAME) alembic upgrade head

.PHONY: create-migration-changes
create-migration-changes: ## Создать новую миграцию для изменений
	@echo "📝 Creating changes tracking migration..."
	docker-compose exec $(SERVICE_NAME) alembic revision --autogenerate -m "Add changes tracking fields"

##@ Advanced Changes Analysis
.PHONY: changes-full-report
changes-full-report: ## Полный отчет по изменениям
	@echo "📋 Full changes report..."
	@echo "\n1. Changes Summary:"
	@make changes-summary
	@echo "\n2. Recent Price Changes:"
	@make recent-price-changes
	@echo "\n3. Price Drops:"
	@make price-drops
	@echo "\n4. Status:"
	@make changes-status

.PHONY: test-changes-pipeline
test-changes-pipeline: ## Тест пайплайна отслеживания изменений
	@echo "🧪 Testing changes tracking pipeline..."
	@echo "1. Status check..."
	@make changes-status
	@echo "\n2. Never checked cars..."
	@make never-checked
	@echo "\n3. Running changes check..."
	@make check-changes

##@ Quick Testing & Debugging
.PHONY: test-changes-system
test-changes-system: ## Полный тест системы отслеживания изменений
	@echo "🧪 Testing complete changes tracking system..."
	@echo "\n1️⃣ Checking system status..."
	@make changes-status
	@echo "\n2️⃣ Getting never checked cars..."
	@make never-checked
	@echo "\n3️⃣ Running changes check with logs..."
	@make check-changes-verbose

.PHONY: debug-car-scraping
debug-car-scraping: ## Отладка скрапинга одной машины (нужен CAR_ID)
	@if [ -z "$(CAR_ID)" ]; then \
		echo "❌ Usage: make debug-car-scraping CAR_ID=123"; \
	else \
		echo "🔍 Debug scraping for car $(CAR_ID)..."; \
		echo "📋 First, get car info from DB:"; \
		curl -s "http://localhost:8000/cars/?filter_name=audi&limit=100" | python3 -c "import sys, json; cars = json.load(sys.stdin); [print(f'🚗 ID: {c[\"id\"]}, Title: {c[\"title\"][:60]}, Link: {c[\"link\"]}') for c in cars if c['id'] == $(CAR_ID)]"; \
		echo "\n🔄 Now testing changes check:"; \
		make test-single-car-change CAR_ID=$(CAR_ID); \
	fi

.PHONY: show-recent-cars
show-recent-cars: ## Показать недавние машины для тестирования
	@echo "🚗 Recent cars for testing:"
	@curl -s "http://localhost:8000/cars/?filter_name=bmw&limit=10" | python3 -c "import sys, json; cars = json.load(sys.stdin); [print(f'🚗 ID: {c[\"id\"]}, Title: {c[\"title\"][:50]}, Price: {c[\"price\"]}') for c in cars[:5]]" 2>/dev/null || echo "No BMW cars found"
	@echo "\n💡 To test: make test-single-car-change CAR_ID=<ID>"
	@echo "💡 To debug: make debug-car-scraping CAR_ID=<ID>"

.PHONY: logs-db-operations
logs-db-operations: ## Логи операций с базой данных
	@echo "🗄️ Database operations logs..."
	docker-compose logs app | grep -E "(update_.*_change|mark_as_unavailable|get_cars_for_changes)" | tail -20
.PHONY: morning-changes
morning-changes: ## Утренний обзор изменений
	@echo "🌅 Morning changes overview..."
	@make changes-summary
	@make price-drops
	@make changes-status

.PHONY: evening-changes
evening-changes: ## Вечерний обзор изменений + отправка alerts
	@echo "🌆 Evening changes overview with alerts..."
	@make changes-summary
	@make price-drops-big
	@make price-drops-alert

##@ Quick Commands (Updated)
.PHONY: full-status
full-status: status ai-status changes-status ## Полный статус всех систем

.PHONY: daily-routine
daily-routine: ## Ежедневная рутина: все проверки + анализ + изменения
	@echo "📅 Daily routine: monitoring + analysis + changes..."
	@make status
	@make database-stats
	@make changes-summary
	@make scheduled-analysis

##@ Help (Updated)
help: ## Show help with new changes commands
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-27s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ""
	@echo "📋 Examples:"
	@echo "  make check-changes                    # Check all cars for changes"
	@echo "  make check-specific-changes CAR_IDS='[123,456]'  # Check specific cars"
	@echo "  make price-drops                      # Show price drops 500€+"
	@echo "  make price-drops-alert                # Send price drops to Telegram"
	@echo "  make changes-full-report              # Complete changes report"
	@echo "  make daily-routine                    # Full daily overview"