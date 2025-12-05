# 🚀 Инструкция по деплою на production сервер

## 📋 Что задеплоено

### Основные изменения:
- ✅ **Admin Analytics Dashboard** - полноценная панель аналитики
- ✅ **Модульная архитектура** - handlers, middlewares, services
- ✅ **Система подписок** - trial, monthly, quarterly, yearly
- ✅ **Промокоды и рефералы** - полноценная система
- ✅ **WebApp для мастера** - управление услугами
- ✅ **Логирование** - профессиональное с rotation
- ✅ **Rate limiting** - защита от спама
- ✅ **112 файлов**, **27,844 строк кода**

---

## 🛠 Подготовка сервера

### 1. Подключитесь к серверу
```bash
ssh your_user@your_server_ip
```

### 2. Установите зависимости
```bash
# Обновите систему
sudo apt update && sudo apt upgrade -y

# Установите Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip -y

# Установите PostgreSQL (если ещё нет)
sudo apt install postgresql postgresql-contrib -y

# Установите Redis (для rate limiting)
sudo apt install redis-server -y
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Установите nginx (для reverse proxy)
sudo apt install nginx -y
```

---

## 📦 Деплой приложения

### 1. Клонируйте репозиторий
```bash
cd /var/www
sudo git clone https://github.com/rosavskiy/BeautyAssist.git
cd BeautyAssist
sudo chown -R $USER:$USER .
```

### 2. Создайте виртуальное окружение
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Настройте .env файл
```bash
cp .env.example .env
nano .env
```

**Заполните следующие переменные:**
```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token
ADMIN_TELEGRAM_IDS=your_telegram_id

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/beautyassist

# Redis
REDIS_URL=redis://localhost:6379/0

# WebApp
WEBAPP_BASE_URL=https://yourdomain.com

# YooKassa (если используете)
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# Other
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### 4. Создайте базу данных
```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE beautyassist;
CREATE USER beautyassist_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE beautyassist TO beautyassist_user;
\q
```

### 5. Примените миграции
```bash
source venv/bin/activate
alembic upgrade head
```

---

## 🌐 Настройка Nginx

### 1. Создайте конфигурацию
```bash
sudo nano /etc/nginx/sites-available/beautyassist
```

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Static files
    location /webapp/ {
        alias /var/www/BeautyAssist/webapp/;
        try_files $uri $uri/ =404;
    }

    # API endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8080;
    }
}
```

### 2. Активируйте конфигурацию
```bash
sudo ln -s /etc/nginx/sites-available/beautyassist /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Установите SSL сертификат (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

---

## 🔄 Настройка systemd сервиса

### 1. Создайте сервис
```bash
sudo nano /etc/systemd/system/beautyassist.service
```

```ini
[Unit]
Description=BeautyAssist Telegram Bot
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/BeautyAssist
Environment="PATH=/var/www/BeautyAssist/venv/bin"
ExecStart=/var/www/BeautyAssist/venv/bin/python -m bot.main
Restart=always
RestartSec=10
StandardOutput=append:/var/log/beautyassist/app.log
StandardError=append:/var/log/beautyassist/error.log

[Install]
WantedBy=multi-user.target
```

### 2. Создайте директорию для логов
```bash
sudo mkdir -p /var/log/beautyassist
sudo chown www-data:www-data /var/log/beautyassist
```

### 3. Запустите сервис
```bash
sudo systemctl daemon-reload
sudo systemctl enable beautyassist
sudo systemctl start beautyassist
```

### 4. Проверьте статус
```bash
sudo systemctl status beautyassist
```

---

## ✅ Проверка работоспособности

### 1. Проверьте логи
```bash
# Логи приложения
tail -f /var/log/beautyassist/app.log

# Логи ошибок
tail -f /var/log/beautyassist/error.log

# Логи systemd
sudo journalctl -u beautyassist -f
```

### 2. Проверьте health endpoint
```bash
curl http://localhost:8080/health
```

Должен вернуть:
```json
{"status": "ok"}
```

### 3. Проверьте через Telegram
- Отправьте `/start` боту
- Проверьте WebApp кнопки
- Откройте admin панель (если вы админ)

### 4. Проверьте WebApp
Откройте в браузере:
- `https://yourdomain.com/webapp/index.html` (клиентская запись)
- `https://yourdomain.com/webapp/admin/analytics.html` (админ панель)

---

## 🔧 Обновление приложения

### 1. Остановите сервис
```bash
sudo systemctl stop beautyassist
```

### 2. Получите обновления
```bash
cd /var/www/BeautyAssist
git pull origin main
source venv/bin/activate
pip install -r requirements.txt --upgrade
alembic upgrade head
```

### 3. Запустите сервис
```bash
sudo systemctl start beautyassist
```

---

## 📊 Мониторинг

### Логи приложения
```bash
# Последние 100 строк
tail -100 /var/log/beautyassist/app.log

# В реальном времени
tail -f /var/log/beautyassist/app.log

# Ошибки за последний час
journalctl -u beautyassist --since "1 hour ago" -p err
```

### Использование ресурсов
```bash
# CPU и память
htop

# Дисковое пространство
df -h

# Активные процессы
ps aux | grep python
```

---

## 🚨 Решение проблем

### Бот не отвечает
1. Проверьте статус сервиса:
   ```bash
   sudo systemctl status beautyassist
   ```

2. Проверьте логи:
   ```bash
   sudo journalctl -u beautyassist -n 50
   ```

3. Проверьте базу данных:
   ```bash
   sudo -u postgres psql -d beautyassist -c "SELECT 1;"
   ```

4. Перезапустите сервис:
   ```bash
   sudo systemctl restart beautyassist
   ```

### WebApp не открывается
1. Проверьте nginx:
   ```bash
   sudo nginx -t
   sudo systemctl status nginx
   ```

2. Проверьте права на файлы:
   ```bash
   ls -la /var/www/BeautyAssist/webapp/
   ```

3. Проверьте логи nginx:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

### Ошибки 404 на admin панели
Если видите ngrok warning page:
- Используйте Cloudflare Tunnel (бесплатно, без ограничений)
- Или настройте nginx reverse proxy
- См. подробности в `FIX_404_WEBAPP.md`

---

## 📚 Документация

После деплоя ознакомьтесь с:
- `ADMIN_ANALYTICS_ACCESS.md` - как работает админ панель
- `FIX_404_WEBAPP.md` - решение проблем с WebApp
- `REFACTORING_SUMMARY.md` - архитектура приложения
- `SPRINT_7_PLAN.md` - план дальнейшего развития

---

## 🎉 Готово!

Приложение задеплоено и готово к использованию на production сервере!

**Основные URL:**
- Бот: `@your_bot_username`
- WebApp: `https://yourdomain.com/webapp/`
- Admin: `https://yourdomain.com/webapp/admin/analytics.html`
- Health: `https://yourdomain.com/health`

**Следующие шаги:**
1. Протестируйте все функции
2. Настройте мониторинг (Sentry, Prometheus)
3. Настройте бэкапы базы данных
4. Добавьте пользователей в бота
5. Начните собирать аналитику

---

**Контакты для поддержки:**
- GitHub Issues: https://github.com/rosavskiy/BeautyAssist/issues
- Telegram: @your_support_username
