# 🚀 Быстрый старт для деплоя BeautyAssist

## Шаг 1: Загрузите скрипты на сервер

```bash
scp server-setup.sh deploy-server.sh root@192.144.59.97:/root/
```

---

## Шаг 2: Первоначальная настройка (ОДИН РАЗ!)

Подключитесь к серверу и выполните:

```bash
ssh root@192.144.59.97

cd /root
chmod +x server-setup.sh deploy-server.sh
./server-setup.sh
```

**После выполнения скрипта:**

1. Отредактируйте `.env`:
```bash
nano /root/BeautyAssist/.env
```

Замените:
- `your_bot_token_here` → токен вашего бота от @BotFather
- `your_secure_password_here` → пароль БД (тот же, что в `server-setup.sh`)
- `your_telegram_id_here` → ваш Telegram ID
- `your-domain.com` → ваш домен

2. Отредактируйте Nginx конфиг:
```bash
nano /etc/nginx/sites-available/beautyassist
```

Замените все `your-domain.com` на ваш реальный домен.

3. Получите SSL сертификат:
```bash
certbot --nginx -d ваш-домен.com
```

4. Запустите бота:
```bash
systemctl start beautyassist-bot
systemctl enable beautyassist-bot
systemctl reload nginx
```

5. Проверьте:
```bash
systemctl status beautyassist-bot
journalctl -u beautyassist-bot -n 20
```

---

## Шаг 3: Деплой обновлений (каждый раз)

Когда вы сделали изменения в коде:

```bash
# 1. На локальной машине: закоммитьте и отправьте в GitHub
git add .
git commit -m "описание изменений"
git push

# 2. На сервере: запустите скрипт деплоя
ssh root@192.144.59.97
cd /root
./deploy-server.sh
```

**Готово! Бот обновлен и перезапущен.**

---

## Проверка работы

```bash
# Статус бота
systemctl status beautyassist-bot

# Логи в реальном времени
journalctl -u beautyassist-bot -f

# Последние 50 строк логов
journalctl -u beautyassist-bot -n 50
```

---

## Если что-то пошло не так

### Бот не запускается

```bash
# Смотрим логи
journalctl -u beautyassist-bot -n 100

# Пробуем запустить вручную
cd /root/BeautyAssist
source venv/bin/activate
python bot/main.py
```

### Проблемы с БД

```bash
# Проверяем PostgreSQL
systemctl status postgresql

# Подключаемся к БД
psql -U beautyassist -d beautyassist_db

# Применяем миграции
cd /root/BeautyAssist
source venv/bin/activate
alembic upgrade head
```

### Nginx не работает

```bash
# Проверяем конфигурацию
nginx -t

# Смотрим логи
tail -f /var/log/nginx/error.log
```

---

## Важные пути

- **Проект:** `/root/BeautyAssist/`
- **Логи бота:** `journalctl -u beautyassist-bot`
- **Конфиг Nginx:** `/etc/nginx/sites-available/beautyassist`
- **Systemd сервис:** `/etc/systemd/system/beautyassist-bot.service`
- **Переменные окружения:** `/root/BeautyAssist/.env`
