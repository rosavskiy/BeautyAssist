# Руководство по безопасности BeautyAssist

**Дата:** 2024-12-06  
**Статус:** В процессе внедрения

## Проблемы безопасности (обнаружены в логах)

### Типы атак в журналах:
```
❌ GET /admin/login.asp - попытки доступа к несуществующим админ-панелям
❌ wget exploit attempts - сканеры уязвимостей
❌ SSL handshake to HTTP port - боты пытаются найти открытые порты
❌ BadStatusLine, BadHttpMessage - некорректные HTTP-запросы
```

### Текущие уязвимости:
- ❌ Порт 8080 открыт для всего интернета (0.0.0.0)
- ❌ Нет reverse proxy (nginx)
- ❌ Нет rate limiting
- ❌ Нет SSL/TLS шифрования
- ❌ Нет защиты от сканеров

---

## ✅ Реализованные меры безопасности

### 1. Изоляция веб-сервера (127.0.0.1)

**Статус:** Код изменён, ожидает деплоя

**Что сделано:**
```python
# bot/main.py
site = web.TCPSite(runner, '127.0.0.1', 8080)  # Было: '0.0.0.0'
```

**Результат:**
- Веб-сервер доступен только с localhost
- Прямой доступ из интернета невозможен
- Требуется nginx для проксирования

**Коммит:** Ожидает: `git commit -m "Security: Bind web server to localhost only"`

---

## 🔄 Ожидают внедрения

### 2. Nginx Reverse Proxy

**Файл конфигурации:** `nginx-beautyassist.conf`

**Установка:**
```bash
# На сервере
sudo apt update && sudo apt install nginx

# Скопировать конфиг
sudo cp nginx-beautyassist.conf /etc/nginx/sites-available/beautyassist

# Активировать
sudo ln -s /etc/nginx/sites-available/beautyassist /etc/nginx/sites-enabled/

# Проверить синтаксис
sudo nginx -t

# Применить
sudo systemctl reload nginx
```

**Защита:**
- ✅ Rate limiting: 10 req/s для API, 30 req/s для WebApp
- ✅ Блокировка `/admin/*` путей
- ✅ Блокировка `.asp`, `.php`, `.cgi`, `.sh` файлов
- ✅ Security headers (X-Frame-Options, X-XSS-Protection)
- ✅ Кэширование статических файлов
- ✅ Логирование подозрительной активности

---

### 3. Firewall (UFW)

**Команды:**
```bash
# Установить UFW (если нет)
sudo apt install ufw

# Разрешить SSH (ВАЖНО! Иначе потеряете доступ)
sudo ufw allow 22/tcp

# Разрешить HTTP/HTTPS для nginx
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Заблокировать прямой доступ к порту 8080 извне
sudo ufw deny 8080/tcp

# Активировать
sudo ufw enable

# Проверить статус
sudo ufw status verbose
```

**Результат:**
- Порт 8080 недоступен извне
- Доступ только через nginx (80/443)

---

### 4. Fail2Ban (автоматическая блокировка атак)

**Установка:**
```bash
sudo apt install fail2ban
```

**Конфигурация:** `/etc/fail2ban/jail.local`
```ini
[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/beautyassist_error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/beautyassist_error.log
maxretry = 10

[nginx-botsearch]
enabled = true
port = http,https
logpath = /var/log/nginx/beautyassist_access.log
maxretry = 5
```

**Применить:**
```bash
sudo systemctl restart fail2ban
sudo fail2ban-client status
```

**Результат:**
- Автоматическая блокировка IP после повторных атак
- Защита от brute-force
- Защита от сканеров

---

### 5. SSL/TLS (Let's Encrypt)

**Установка Certbot:**
```bash
sudo apt install certbot python3-certbot-nginx
```

**Получить сертификат:**
```bash
sudo certbot --nginx -d v2992624.hosted-by-vdsina.ru
```

**Авто-обновление:**
```bash
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

**Результат:**
- Шифрование трафика
- Защита от MITM-атак
- HTTPS для всех WebApp

---

## 📋 Чек-лист внедрения

### Этап 1: Базовая изоляция (5 минут)
- [x] Изменить bind с `0.0.0.0` на `127.0.0.1` в `bot/main.py`
- [ ] Закоммитить и задеплоить изменение
- [ ] Проверить, что бот запустился: `sudo systemctl status beautyassist-bot`
- [ ] Убедиться, что прямой доступ к порту 8080 извне НЕ работает

### Этап 2: Nginx (10 минут)
- [ ] Установить nginx: `sudo apt install nginx`
- [ ] Загрузить конфиг на сервер
- [ ] Активировать конфиг
- [ ] Проверить синтаксис: `sudo nginx -t`
- [ ] Перезагрузить nginx: `sudo systemctl reload nginx`
- [ ] Протестировать WebApp через nginx (http://server-ip/webapp-master/)

### Этап 3: Firewall (5 минут)
- [ ] Установить UFW
- [ ] **КРИТИЧНО:** Разрешить SSH перед активацией!
- [ ] Настроить правила (порты 22, 80, 443 открыты; 8080 закрыт)
- [ ] Активировать: `sudo ufw enable`
- [ ] Проверить: `sudo ufw status`

### Этап 4: Fail2Ban (5 минут)
- [ ] Установить fail2ban
- [ ] Создать `/etc/fail2ban/jail.local` с конфигурацией
- [ ] Перезапустить: `sudo systemctl restart fail2ban`
- [ ] Проверить статус: `sudo fail2ban-client status`

### Этап 5: SSL (опционально, 10 минут)
- [ ] Установить certbot
- [ ] Получить сертификат для домена
- [ ] Раскомментировать HTTPS-блок в nginx конфиге
- [ ] Перезагрузить nginx

---

## 🧪 Тестирование безопасности

### 1. Проверка изоляции порта 8080
```bash
# С локальной машины (должно НЕ работать)
curl http://v2992624.hosted-by-vdsina.ru:8080/

# На сервере (должно работать)
curl http://127.0.0.1:8080/
```

### 2. Проверка nginx reverse proxy
```bash
# Должно работать через nginx
curl http://v2992624.hosted-by-vdsina.ru/webapp-master/

# Проверка заблокированных путей
curl http://v2992624.hosted-by-vdsina.ru/admin/  # → 404
curl http://v2992624.hosted-by-vdsina.ru/test.php  # → 404
```

### 3. Проверка rate limiting
```bash
# Быстрые повторные запросы (должны получить 429 Too Many Requests)
for i in {1..50}; do curl http://v2992624.hosted-by-vdsina.ru/api/; done
```

### 4. Проверка firewall
```bash
# На сервере
sudo ufw status verbose

# Должно показать:
# 8080/tcp DENY IN Anywhere
# 80/tcp ALLOW IN Anywhere
# 443/tcp ALLOW IN Anywhere
```

### 5. Мониторинг атак
```bash
# Логи nginx - подозрительная активность
sudo tail -f /var/log/nginx/beautyassist_error.log

# Логи fail2ban - заблокированные IP
sudo fail2ban-client status nginx-botsearch

# Журнал бота (должно быть меньше ошибок BadStatusLine)
sudo journalctl -u beautyassist-bot -f --since "5 minutes ago"
```

---

## 📊 Ожидаемый результат

**До:**
```
❌ Атаки в логах: BadStatusLine, wget exploits, /admin/login.asp
❌ Порт 8080 открыт для всех
❌ Нет rate limiting
❌ Нет шифрования
```

**После:**
```
✅ Порт 8080 доступен только localhost
✅ Все запросы через nginx (rate limiting + блокировка атак)
✅ Firewall блокирует прямой доступ к 8080
✅ Fail2Ban автоматически банит атакующих
✅ (опционально) SSL/TLS шифрование
✅ Логи nginx фильтруют атаки ДО попадания в бот
```

---

## 🚀 Быстрый деплой всех мер (30 минут)

```bash
# 1. Деплой изменений бота
cd /var/www/BeautyAssist
git pull origin main
sudo systemctl restart beautyassist-bot

# 2. Установить nginx + UFW + fail2ban
sudo apt update
sudo apt install -y nginx ufw fail2ban

# 3. Настроить firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8080/tcp
sudo ufw enable

# 4. Настроить nginx
sudo cp nginx-beautyassist.conf /etc/nginx/sites-available/beautyassist
sudo ln -s /etc/nginx/sites-available/beautyassist /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 5. Настроить fail2ban
sudo nano /etc/fail2ban/jail.local  # Вставить конфигурацию выше
sudo systemctl restart fail2ban

# 6. Проверить всё работает
curl http://localhost/webapp-master/
sudo systemctl status beautyassist-bot nginx fail2ban
sudo ufw status
```

---

## 📝 Дополнительные рекомендации

### 1. Регулярный мониторинг
```bash
# Еженедельно проверять логи атак
sudo tail -100 /var/log/nginx/beautyassist_error.log | grep -i "error\|attack\|exploit"

# Проверять статус fail2ban
sudo fail2ban-client status
```

### 2. Обновления системы
```bash
# Ежемесячно
sudo apt update && sudo apt upgrade
sudo systemctl restart beautyassist-bot nginx
```

### 3. Backup конфигураций
```bash
# Сохранить копии конфигов
sudo tar -czf /root/security-backup-$(date +%F).tar.gz \
  /etc/nginx/sites-available/beautyassist \
  /etc/fail2ban/jail.local \
  /etc/ufw/
```

---

## ❓ FAQ

**Q: Будет ли работать WebApp после этих изменений?**  
A: Да, все URL останутся теми же. Nginx прозрачно проксирует запросы к боту.

**Q: Что если я потеряю SSH-доступ?**  
A: ПЕРЕД `ufw enable` ОБЯЗАТЕЛЬНО выполните `ufw allow 22/tcp`. Если забыли - нужен доступ к консоли через панель VDS.

**Q: Как откатить изменения?**  
A: 
```bash
# Откатить bind на 0.0.0.0
cd /var/www/BeautyAssist
git revert HEAD
sudo systemctl restart beautyassist-bot

# Отключить firewall
sudo ufw disable
```

**Q: Нужен ли SSL, если бот работает только через Telegram WebApp?**  
A: Желательно. Telegram WebApp требует HTTPS для некоторых API (геолокация, камера). Плюс шифрование трафика - хорошая практика.

---

**Следующий шаг:** Задеплоить изменение `bot/main.py` и настроить nginx.
