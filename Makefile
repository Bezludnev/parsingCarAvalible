-include .env
export

# Project settings
PROJECT_NAME ?= car-monitor
SERVICE_NAME ?= app
PYTHON_VERSION ?= 3.11
BUILD_TIME ?= $(shell date -Iseconds)

.DEFAULT_GOAL := help
.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-27s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development
.PHONY: setup
setup: ## Setup environment and install dependencies
	@echo "🔧 Setting up development environment..."
	@if [ ! -f .env ]; then cp .env.example .env; echo "📄 Created .env from example"; fi
	@echo "✅ Setup complete! Edit .env with your tokens"

.PHONY: install
install: ## Install Python dependencies locally
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

.PHONY: dev
dev: ## Run FastAPI locally (without Docker)
	@echo "🚀 Starting FastAPI development server..."
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

##@ Docker Operations
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

##@ Database
.PHONY: db-shell
db-shell: ## Connect to MySQL shell
	docker-compose exec mysql mysql -u caruser -pcarpass car_monitor

.PHONY: db-reset
db-reset: ## Reset database (DESTRUCTIVE)
	@echo "💀 Resetting database..."
	docker-compose down
	docker volume rm $(shell docker-compose config --volumes | grep mysql) 2>/dev/null || true
	docker-compose up -d mysql
	@echo "⏳ Waiting for MySQL..."
	sleep 10
	docker-compose up -d $(SERVICE_NAME)

.PHONY: migrate
migrate: ## Apply Alembic migrations
	@echo "📈 Updating database migrations..."
	docker-compose exec $(SERVICE_NAME) alembic upgrade head

##@ Monitoring & Logs
.PHONY: logs
logs: ## Show all logs
	docker-compose logs -f

.PHONY: logs-app
logs-app: ## Show app logs only
	docker-compose logs -f $(SERVICE_NAME)

.PHONY: logs-mysql
logs-mysql: ## Show MySQL logs
	docker-compose logs -f mysql

.PHONY: ps
ps: ## Show running containers
	docker-compose ps

.PHONY: stats
stats: ## Show container stats
	docker stats $(shell docker-compose ps -q)

##@ Testing & Quality
.PHONY: shell
shell: ## Enter app container shell
	docker-compose exec $(SERVICE_NAME) /bin/bash

.PHONY: test
test: ## Run tests (if any)
	@echo "🧪 Running tests..."
	docker-compose exec $(SERVICE_NAME) python -m pytest tests/ -v || echo "No tests found"

.PHONY: format
format: ## Format Python code
	@echo "🎨 Formatting code..."
	docker-compose exec $(SERVICE_NAME) python -m black app/ --line-length 100 || echo "Install black for formatting"

.PHONY: lint
lint: ## Lint Python code
	@echo "🔍 Linting code..."
	docker-compose exec $(SERVICE_NAME) python -m flake8 app/ || echo "Install flake8 for linting"

##@ API Testing
.PHONY: check-health
check-health: ## Check API health
	@echo "🏥 Checking API health..."
	curl -s http://localhost:8000/health | python -m json.tool || echo "API not responding"

.PHONY: trigger-scraping
trigger-scraping: ## Manual trigger car scraping
	@echo "🔍 Triggering manual scraping..."
	curl -X POST http://localhost:8000/cars/check-now | python -m json.tool

.PHONY: ai-analysis
ai-analysis: ## Run AI analysis for Mercedes
	@echo "🤖 Running AI analysis..."
	curl -X POST "http://localhost:8000/analysis/by-filter/mercedes?limit=10" | python -m json.tool

.PHONY: quick-analysis
quick-analysis: ## Quick AI analysis
	@echo "⚡ Quick analysis..."
	curl -s http://localhost:8000/analysis/quick/mercedes | python -m json.tool

##@ Advanced
.PHONY: backup-db
backup-db: ## Backup database
	@echo "💾 Creating database backup..."
	docker-compose exec mysql mysqldump -u caruser -pcarpass car_monitor > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup saved"

.PHONY: clean-images
clean-images: ## Clean unused Docker images
	@echo "🧹 Cleaning Docker images..."
	docker image prune -f

.PHONY: update-chrome
update-chrome: ## Force Chrome/ChromeDriver update
	@echo "🌐 Updating Chrome and ChromeDriver..."
	docker-compose build --no-cache $(SERVICE_NAME)

##@ Quick Commands
.PHONY: fresh
fresh: clear rebuild ## Complete fresh start (DESTRUCTIVE)

.PHONY: quick
quick: restart logs-app ## Quick restart and show logs

.PHONY: status
status: ps check-health ## Show status and health

##@ Development Workflow
.PHONY: code-reload
code-reload: ## Reload code without full restart (fastest)
	@echo "⚡ Hot reloading code..."
	docker-compose exec $(SERVICE_NAME) pkill -HUP -f uvicorn || echo "Restarting container..."
	docker-compose restart $(SERVICE_NAME)

.PHONY: dev-cycle
dev-cycle: code-reload logs-app ## Development cycle: reload + logs