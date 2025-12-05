# 🚀 Быстрый старт после рефакторинга

## Запуск бота

### Через venv (рекомендуется):
```bash
.\venv\Scripts\python.exe -m bot.main
```

### Через системный Python:
```bash
python -m bot.main
```

## Проверка работоспособности

### 1. Логи
Все логи сохраняются в `logs/`:
- `beautyassist.log` - основные логи (JSON format)
- `errors.log` - только ошибки

```bash
# Просмотр последних логов
Get-Content logs\beautyassist.log -Tail 50

# Мониторинг в реальном времени
Get-Content logs\beautyassist.log -Wait
```

### 2. Health Check
```bash
curl http://localhost:8080/health
# Ответ: {"status": "ok"}
```

### 3. API Endpoints

**Список услуг:**
```bash
curl "http://localhost:8080/api/services?master_id=123"
```

**Информация о клиенте:**
```bash
curl "http://localhost:8080/api/client/info?phone=79991234567&master_id=123"
```

**Доступные слоты:**
```bash
curl "http://localhost:8080/api/slots?master_id=123&service_id=1&date=2025-12-05"
```

## Структура проекта после рефакторинга

```
bot/
├── main.py (127 строк) ⭐ - точка входа
├── config.py - настройки + CITY_TZ_MAP
├── logging_config.py - JSON logging с rotation
│
├── handlers/
│   ├── __init__.py - регистрация handlers
│   ├── onboarding.py - /start, регистрация
│   ├── master.py - команды мастера
│   ├── appointments.py - callbacks записей
│   └── api.py - REST API (20+ endpoints)
│
├── middlewares/
│   ├── __init__.py - setup_middlewares()
│   ├── logging.py - запись событий
│   ├── error_handler.py - обработка ошибок
│   ├── throttling.py - rate limiting
│   └── auth.py - проверка регистрации
│
├── utils/
│   ├── webapp.py - генерация WebApp URL
│   ├── formatters.py - форматирование текста
│   └── time_utils.py - работа с временем
│
└── keyboards/
    ├── client.py - клавиатуры для клиентов
    └── master.py - клавиатуры для мастеров

services/
├── scheduler.py - вычисление слотов
├── notifications.py - отправка уведомлений
├── incomplete_checker.py - проверка незавершённых
└── reminder_tasks.py ⭐ - фоновые задачи

database/
├── base.py - инициализация БД
├── models/ - SQLAlchemy модели
└── repositories/ - data access layer
```

## Основные компоненты

### 1. Handlers
Все обработчики используют Router pattern:
```python
from aiogram import Router
router = Router(name="onboarding")

@router.message(CommandStart())
async def on_start(message: Message):
    ...

def register_handlers(dp):
    dp.include_router(router)
```

### 2. Middleware
Порядок выполнения:
1. LoggingMiddleware - логирование
2. ErrorHandlerMiddleware - обработка ошибок
3. ThrottlingMiddleware - rate limiting (5 req/min)
4. AuthMiddleware - проверка регистрации

### 3. API
Все endpoints в `bot/handlers/api.py`:
```python
def setup_routes(app: web.Application):
    app.router.add_get('/health', health_check)
    app.router.add_get('/api/services', get_services)
    # ... 20+ endpoints
```

### 4. Background Tasks
APScheduler с 2 задачами:
- `scan_and_send_reminders` - каждую минуту
- `check_incomplete_appointments` - ежедневно в 9:00

### 5. Logging
JSON structured logs:
```json
{
  "timestamp": "2025-12-04T13:22:35.367443Z",
  "level": "INFO",
  "logger": "__main__",
  "message": "Starting BeautyAssist bot...",
  "module": "main",
  "function": "main",
  "line": 87
}
```

## Конфигурация

### .env файл (пример):
```env
# Telegram
BOT_TOKEN=your_bot_token_here
BOT_USERNAME=your_bot_username

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/beautyassist

# Redis
REDIS_URL=redis://localhost:6379/0

# WebApp
WEBAPP_BASE_URL=https://yourdomain.com

# Environment
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
```

## Troubleshooting

### Ошибка: "No module named 'redis'"
```bash
.\venv\Scripts\python.exe -m pip install redis==5.2.0
```

### Ошибка: "Database connection failed"
Проверьте DATABASE_URL в .env и запустите миграции:
```bash
alembic upgrade head
```

### Ошибка: "Throttling middleware failed"
Убедитесь, что Redis запущен:
```bash
redis-cli ping
# Ответ: PONG
```

### Логи не создаются
Проверьте права на папку `logs/`:
```bash
New-Item -ItemType Directory -Path logs -Force
```

## Команды для разработки

### Запуск с горячей перезагрузкой (watchdog):
```bash
# Установить watchdog
pip install watchdog

# Запустить с мониторингом
watchmedo auto-restart --directory=bot --pattern=*.py --recursive -- python -m bot.main
```

### Форматирование кода:
```bash
pip install black isort
black bot/
isort bot/
```

### Проверка типов:
```bash
pip install mypy
mypy bot/
```

### Запуск тестов:
```bash
pytest tests/
```

## Полезные ссылки

- **Документация aiogram**: https://docs.aiogram.dev/
- **Документация aiohttp**: https://docs.aiohttp.org/
- **SQLAlchemy async**: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **APScheduler**: https://apscheduler.readthedocs.io/

## Метрики

- **Размер кодовой базы**: ~3,500 строк (было 2,549 в одном файле)
- **Модулей**: 12+
- **Middleware**: 4
- **API endpoints**: 20+
- **Handlers**: 3 (onboarding, master, appointments)
- **Background tasks**: 2
- **Время запуска**: ~0.5s
- **Сокращение main.py**: 95% (2549 → 127 строк)

---

**Обновлено**: 4 декабря 2025 г.  
**Версия**: 2.0 (после рефакторинга)
