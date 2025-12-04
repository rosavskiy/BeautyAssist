# Руководство по локальной разработке

## Настройка окружения для разработки

### 1. Создание DEV бота

1. Откройте Telegram и найдите [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания нового бота
4. Сохраните полученный токен - он понадобится для `.env`
5. **Важно:** Используйте отдельного бота для разработки, чтобы не мешать работе production бота

### 2. Установка ngrok

ngrok необходим для тестирования webhook локально.

**Windows:**
```powershell
# Скачайте ngrok с https://ngrok.com/download
# Или установите через Chocolatey:
choco install ngrok

# Зарегистрируйтесь на ngrok.com и получите authtoken
ngrok config add-authtoken YOUR_AUTHTOKEN
```

**Linux/macOS:**
```bash
# Скачайте и распакуйте
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-v3-stable-linux-amd64.tgz

# Добавьте authtoken
./ngrok config add-authtoken YOUR_AUTHTOKEN
```

### 3. Настройка локальной базы данных

**PostgreSQL:**
```powershell
# Создайте базу данных для разработки
psql -U postgres
CREATE DATABASE beautyassist_dev;
CREATE USER beautyassist_dev WITH PASSWORD 'dev_password';
GRANT ALL PRIVILEGES ON DATABASE beautyassist_dev TO beautyassist_dev;
\q
```

**Или используйте Docker:**
```powershell
docker run --name postgres-dev -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:15
```

### 4. Создание .env файла

```powershell
# Скопируйте шаблон для разработки
Copy-Item .env.development .env

# Отредактируйте .env и укажите:
# - BOT_TOKEN от вашего DEV бота
# - DATABASE_URL для локальной БД
# - Остальные параметры можно оставить как в шаблоне
```

### 5. Установка зависимостей

```powershell
# Создайте виртуальное окружение
python -m venv venv

# Активируйте его
.\venv\Scripts\Activate.ps1

# Установите зависимости
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Примените миграции
alembic upgrade head
```

## Запуск для разработки

### Шаг 1: Запустите ngrok

```powershell
# В отдельном терминале запустите ngrok
ngrok http 8080
```

Вы увидите что-то вроде:
```
Forwarding   https://1234-5678-90ab-cdef.ngrok-free.app -> http://localhost:8080
```

### Шаг 2: Обновите WEBHOOK_URL в .env

Скопируйте HTTPS URL из ngrok и обновите `.env`:
```
WEBHOOK_URL=https://1234-5678-90ab-cdef.ngrok-free.app
```

**Важно:** После каждого перезапуска ngrok URL меняется, поэтому нужно обновлять `.env`!

### Шаг 3: Запустите бота

```powershell
# Убедитесь, что виртуальное окружение активно
python -m bot.main
```

### Шаг 4: Тестируйте изменения

1. Откройте Telegram и найдите вашего DEV бота
2. Начните с `/start`
3. Все изменения в коде будут работать только с DEV ботом
4. Production бот (@mybeautyassist_bot) продолжит работать независимо

## Рабочий процесс

### Внесение изменений

```powershell
# 1. Создайте новую ветку для фичи
git checkout -b feature/my-new-feature

# 2. Вносите изменения в коде
# 3. Тестируйте локально с DEV ботом

# 4. Запустите тесты
pytest

# 5. Коммитьте изменения
git add .
git commit -m "Add new feature"

# 6. Отправьте в GitHub
git push origin feature/my-new-feature
```

### Деплой в production

```powershell
# 1. Merge в main через Pull Request на GitHub

# 2. На сервере запустите деплой скрипт
ssh root@192.144.59.97
cd /root/BeautyAssist
bash deploy-server.sh
```

## Полезные команды

### База данных

```powershell
# Создать новую миграцию
alembic revision --autogenerate -m "Description"

# Применить миграции
alembic upgrade head

# Откатить миграцию
alembic downgrade -1

# Показать историю миграций
alembic history
```

### Тестирование

```powershell
# Запустить все тесты
pytest

# Запустить конкретный тест
pytest tests/test_slots.py

# С покрытием кода
pytest --cov=bot --cov-report=html
```

### Проверка кода

```powershell
# Форматирование
black bot/ database/ services/

# Линтер
ruff check bot/ database/ services/

# Проверка типов
mypy bot/ database/ services/
```

## Переменные окружения

### Основные переменные для разработки

| Переменная | Описание | Пример |
|-----------|----------|---------|
| `ENVIRONMENT` | Режим работы | `development` |
| `BOT_TOKEN` | Токен DEV бота | `123456:ABC-DEF...` |
| `BOT_USERNAME` | Username DEV бота | `my_dev_bot` |
| `WEBHOOK_URL` | ngrok URL | `https://xxx.ngrok-free.app` |
| `DATABASE_URL` | Локальная БД | `postgresql+asyncpg://...` |
| `DEBUG` | Отладочный режим | `true` |
| `LOG_LEVEL` | Уровень логов | `DEBUG` |

## Типичные проблемы

### ngrok URL изменился

**Проблема:** После перезапуска ngrok бот не получает обновления.

**Решение:**
1. Обновите `WEBHOOK_URL` в `.env`
2. Перезапустите бота

### Конфликт с production

**Проблема:** Случайно запустили production бота локально.

**Решение:**
1. Убедитесь, что в `.env` указан токен DEV бота
2. Проверьте `ENVIRONMENT=development`
3. Используйте `.env.development` как шаблон

### База данных не найдена

**Проблема:** `asyncpg.InvalidCatalogNameError`

**Решение:**
```powershell
# Создайте базу данных
psql -U postgres -c "CREATE DATABASE beautyassist_dev;"

# Примените миграции
alembic upgrade head
```

### Webhook не работает

**Проблема:** Бот не получает сообщения.

**Решение:**
1. Проверьте, что ngrok запущен: `ngrok http 8080`
2. URL в `.env` соответствует URL из ngrok
3. В логах бота должна быть строка: `Webhook set successfully`
4. Проверьте: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`

## VS Code Configuration

### Рекомендуемые расширения

- Python (Microsoft)
- Pylance
- Python Test Explorer
- GitLens
- Better Comments

### settings.json

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/Scripts/python.exe",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"],
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

## Дополнительные ресурсы

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [aiogram Documentation](https://docs.aiogram.dev/)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/en/20/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [ngrok Documentation](https://ngrok.com/docs)
