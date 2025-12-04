# Управление окружениями

## Обзор

BeautyAssist поддерживает несколько окружений:
- **development** - локальная разработка с DEV ботом и ngrok
- **production** - production сервер с реальным ботом

## Переменная ENVIRONMENT

Окружение определяется переменной `ENVIRONMENT` в `.env`:

```bash
ENVIRONMENT=development  # для локальной разработки
ENVIRONMENT=production   # для production сервера
```

Если переменная не указана, по умолчанию используется `development`.

## Шаблоны конфигурации

### .env.development (для локальной разработки)

```bash
# Скопируйте шаблон
cp .env.development .env

# Отредактируйте:
# - BOT_TOKEN: создайте DEV бота через @BotFather
# - WEBHOOK_URL: укажите ngrok URL (https://xxxx.ngrok-free.app)
# - DATABASE_URL: укажите локальную БД
```

**Ключевые отличия development:**
- Используется отдельный DEV бот (не влияет на production)
- Webhook через ngrok (перезапуск ngrok требует обновления URL)
- Локальная PostgreSQL база данных
- DEBUG=true, LOG_LEVEL=DEBUG
- Более свободные лимиты для тестирования

### .env.production (для production сервера)

```bash
# На сервере скопируйте шаблон
cp .env.production .env

# Отредактируйте:
# - DATABASE_URL: укажите пароль БД
# - PAYMENT_PROVIDER_TOKEN: укажите реальный токен оплаты
```

**Ключевые отличия production:**
- Используется основной production бот (@mybeautyassist_bot)
- Webhook на реальный домен с SSL (https://mybeautyassist.ru)
- Production PostgreSQL база данных
- DEBUG=false, LOG_LEVEL=INFO
- Реальные лимиты для пользователей

## Различия конфигураций

| Параметр | Development | Production |
|----------|-------------|------------|
| `ENVIRONMENT` | `development` | `production` |
| `BOT_TOKEN` | DEV бот | Production бот |
| `WEBHOOK_URL` | ngrok URL | https://mybeautyassist.ru |
| `DATABASE_URL` | localhost:5432/beautyassist_dev | localhost:5432/beautyassist_db |
| `DEBUG` | `true` | `false` |
| `LOG_LEVEL` | `DEBUG` | `INFO` |
| `FREEMIUM_MAX_CLIENTS` | 100 | 50 |
| `FREEMIUM_MAX_SERVICES` | 50 | 20 |
| `FREEMIUM_MAX_APPOINTMENTS_PER_MONTH` | 1000 | 200 |

## Локальная разработка

### Шаг 1: Создайте DEV бота

```
1. Откройте @BotFather в Telegram
2. Отправьте /newbot
3. Следуйте инструкциям
4. Сохраните токен
```

### Шаг 2: Настройте .env

```powershell
# Скопируйте шаблон
Copy-Item .env.development .env

# Откройте .env и укажите:
# - BOT_TOKEN=ваш_dev_токен
# - DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/beautyassist_dev
```

### Шаг 3: Запустите ngrok

```powershell
# В отдельном терминале
ngrok http 8080

# Скопируйте HTTPS URL (например: https://1234-5678.ngrok-free.app)
# Обновите WEBHOOK_URL в .env
```

### Шаг 4: Запустите бота

```powershell
# Активируйте venv
.\venv\Scripts\Activate.ps1

# Запустите бота
python -m bot.main
```

### Шаг 5: Тестируйте

- Откройте Telegram и найдите вашего DEV бота
- Все изменения тестируются только на DEV боте
- Production бот продолжает работать независимо

## Production деплой

### Первоначальная настройка

```bash
# На сервере
cd /root/BeautyAssist

# Скопируйте шаблон
cp .env.production .env

# Отредактируйте .env (укажите пароль БД)
nano .env

# Запустите setup скрипт
bash server-setup.sh
```

### Обновление кода

```bash
# На сервере
cd /root/BeautyAssist
bash deploy-server.sh
```

Скрипт автоматически:
1. Подтягивает последние изменения из GitHub
2. Устанавливает новые зависимости
3. Применяет миграции БД
4. Перезапускает бота

## Переключение между окружениями

### Из development в production

```powershell
# 1. Закоммитьте изменения
git add .
git commit -m "Add new feature"
git push origin main

# 2. На сервере выполните деплой
ssh root@192.144.59.97
cd /root/BeautyAssist
bash deploy-server.sh
```

### Из production в development

```powershell
# 1. Получите последние изменения
git pull origin main

# 2. Обновите зависимости
pip install -r requirements.txt --upgrade

# 3. Примените миграции
alembic upgrade head

# 4. Перезапустите бота локально
python -m bot.main
```

## Проверка текущего окружения

```python
# В коде
from bot.config import settings
print(f"Current environment: {settings.environment}")
```

```powershell
# В терминале (PowerShell)
Select-String -Path .env -Pattern "^ENVIRONMENT="

# В терминале (bash)
grep "^ENVIRONMENT=" .env
```

## Лучшие практики

### ✅ DO

- Используйте отдельного DEV бота для локальной разработки
- Коммитьте изменения в `.env.development` и `.env.production` (это шаблоны)
- НЕ коммитьте реальный `.env` файл (он в .gitignore)
- Тестируйте все изменения локально перед деплоем
- После перезапуска ngrok обновляйте `WEBHOOK_URL` в `.env`

### ❌ DON'T

- НЕ используйте production токен локально
- НЕ коммитьте реальные токены и пароли
- НЕ деплойте в production непротестированный код
- НЕ изменяйте production `.env` напрямую на сервере без резервной копии

## Troubleshooting

### Локальная разработка использует production бота

**Проблема:** В логах видны записи от production пользователей.

**Решение:**
```powershell
# Проверьте .env
Select-String -Path .env -Pattern "BOT_TOKEN|ENVIRONMENT"

# Должно быть:
# ENVIRONMENT=development
# BOT_TOKEN=<токен_dev_бота>

# Если используется production токен, исправьте и перезапустите
```

### ngrok URL не работает после перезапуска

**Проблема:** Бот не получает сообщения после перезапуска ngrok.

**Решение:**
```powershell
# 1. Скопируйте новый URL из ngrok
# 2. Обновите .env
# 3. Перезапустите бота
```

### База данных не найдена в production

**Проблема:** `asyncpg.InvalidCatalogNameError` на сервере.

**Решение:**
```bash
# На сервере проверьте DATABASE_URL
cat .env | grep DATABASE_URL

# Проверьте существование БД
sudo -u postgres psql -c "\l" | grep beautyassist
```

### Конфликт миграций между dev и production

**Проблема:** Alembic показывает расхождения версий.

**Решение:**
```bash
# Проверьте текущую версию
alembic current

# Откатите на известную версию
alembic downgrade <revision>

# Примените все миграции
alembic upgrade head
```

## Дополнительные окружения

### Staging (опционально)

Если нужно staging окружение:

```bash
# Создайте .env.staging
cp .env.production .env.staging

# Измените:
# - ENVIRONMENT=staging
# - BOT_TOKEN=<staging_bot_token>
# - DATABASE_URL=<staging_database>
# - WEBHOOK_URL=<staging_domain>
```

## Автоматизация

### Git hooks (pre-push)

Создайте `.git/hooks/pre-push` для автоматической проверки:

```bash
#!/bin/bash
# Проверка, что не коммитятся production токены

if grep -r "8583218102:AAGDk" .env 2>/dev/null; then
    echo "ERROR: Production token found in .env!"
    exit 1
fi

echo "Pre-push checks passed"
exit 0
```

```powershell
# Сделайте hook исполняемым
chmod +x .git/hooks/pre-push
```

## Мониторинг окружений

### Development

```powershell
# Проверка статуса
python -m bot.main  # Логи в консоль

# Просмотр БД
psql -U postgres -d beautyassist_dev
```

### Production

```bash
# Проверка статуса сервиса
systemctl status beautyassist-bot

# Просмотр логов
journalctl -u beautyassist-bot -f

# Проверка БД
sudo -u postgres psql -d beautyassist_db
```
