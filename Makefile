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
