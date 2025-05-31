# Car Monitor Bot v2.1 - с HTML отчетами

Telegram бот для мониторинга автомобилей на Bazaraki с AI анализом через o3-mini и генерацией HTML отчетов.

## 🆕 Новые возможности v2.1

### 📄 HTML отчеты
- **Полные отчеты** сохраняются как красивые HTML файлы
- **Краткие выжимки** отправляются в Telegram (в пределах лимита 4000 символов)
- **Автоматическая отправка** HTML файлов в Telegram как документы
- **API для управления** отчетами (скачивание, очистка, статистика)

### 🤖 Оптимизированные уведомления
- Telegram получает только самое важное
- Полный анализ доступен в HTML файле
- Рекомендованные ID машин в кратком формате
- Уведомления о создании отчетов

## 📋 API Endpoints

### Анализ
- `POST /analysis/by-filter/{filter_name}` - Анализ по фильтру
- `POST /analysis/send-to-telegram/{filter_name}` - Отправить анализ в Telegram
- `GET /analysis/status` - Статус AI сервиса

### HTML отчеты  
- `GET /reports/list` - Список созданных отчетов
- `GET /reports/download/{filename}` - Скачать отчет
- `DELETE /reports/cleanup` - Удалить старые отчеты
- `POST /reports/send-list-to-telegram` - Список отчетов в Telegram
- `GET /reports/stats` - Статистика отчетов

### Мониторинг
- `POST /cars/check-now` - Ручная проверка новых машин
- `GET /health` - Статус системы

## 🔧 Установка и запуск

1. **Клонировать репозиторий**
```bash
git clone <repo_url>
cd parsingCarAvalible
```

2. **Настроить .env файл**
```bash
cp .env.example .env
# Заполнить TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, OPENAI_API_KEY
```

3. **Запустить через Docker**
```bash
docker-compose up -d
```

4. **Проверить работу**
```bash
curl http://localhost:8000/health
```

## 📁 Структура отчетов

HTML отчеты сохраняются в директории `reports/` с именами:
```
ai_analysis_mercedes_15cars_20241231_143022.html
ai_analysis_bmw_8cars_20241231_143055.html
ai_comparison_3cars_20241231_143105.html
```

## 🤖 AI анализ

Использует модель **o3-mini** через новый Responses API:
- Анализ надежности и типичных проблем моделей
- Оценка соответствия цены рынку Кипра  
- Учет климатических особенностей
- Прогноз расходов на обслужива