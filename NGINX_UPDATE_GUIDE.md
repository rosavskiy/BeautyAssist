# Инструкция по обновлению nginx конфига

## ⚠️ ВАЖНО: Ваш текущий конфиг имеет проблемы

### Найденные уязвимости:
1. ❌ **WebApp раздаётся через `alias`** - статика идёт напрямую, минуя бот
   - Проблема: Нет rate limiting для статики
   - Проблема: Бот не контролирует доступ
   
2. ❌ **Нет блокировки атак** - все запросы доходят до бота
   - `/admin/login.asp` → попадает в бот → ошибки в логах
   - `.php`, `.asp` файлы → попадают в бот → BadStatusLine
   
3. ❌ **Нет rate limiting** - можно DDoS
   
4. ❌ **Нет security headers** - XSS уязвимости
   
5. ❌ **Нет отдельного лога для блокировок** - непонятно что фильтруется

---

## 🔧 Как применить исправленный конфиг

### Шаг 1: Backup текущего конфига (1 мин)
```bash
sudo cp /etc/nginx/sites-available/beautyassist /etc/nginx/sites-available/beautyassist.backup-$(date +%Y%m%d)
```

### Шаг 2: Загрузить новый конфиг на сервер (2 мин)

**Вариант А: Через SCP (с вашей машины)**
```powershell
# Из папки D:\Projects\BeautyAssist
scp nginx-beautyassist-fixed.conf root@v2992624.hosted-by-vdsina.ru:/tmp/
```

**Вариант Б: Через nano (на сервере)**
```bash
# На сервере
sudo nano /etc/nginx/sites-available/beautyassist
# Скопировать содержимое из nginx-beautyassist-fixed.conf
# Ctrl+X → Y → Enter
```

**Вариант В: Через git (на сервере)**
```bash
cd /var/www/BeautyAssist
git pull origin main
sudo cp nginx-beautyassist-fixed.conf /etc/nginx/sites-available/beautyassist
```

### Шаг 3: Проверить синтаксис (1 мин)
```bash
sudo nginx -t
```

**Ожидаемый вывод:**
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### Шаг 4: Применить изменения (1 мин)
```bash
sudo systemctl reload nginx
```

### Шаг 5: Проверить работу (2 мин)
```bash
# 1. WebApp должен работать
curl -I https://mybeautyassist.ru/webapp-master/

# 2. API должен работать
curl -I https://mybeautyassist.ru/api/

# 3. Атаки должны блокироваться
curl -I https://mybeautyassist.ru/admin/login.asp  # → 404
curl -I https://mybeautyassist.ru/test.php         # → 404

# 4. Rate limiting работает (после 30+ быстрых запросов)
for i in {1..40}; do curl -I https://mybeautyassist.ru/api/ 2>&1 | grep HTTP; done
# Должны появиться: HTTP/2 429 (Too Many Requests)
```

---

## 📊 Что изменилось

### ✅ Добавлено:

**1. Rate Limiting:**
```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=webapp_limit:10m rate=30r/s;
```
- API: максимум 10 запросов/сек + burst 20
- WebApp: максимум 30 запросов/сек + burst 50

**2. Блокировка атак:**
```nginx
location ~ /admin/ { return 404; }
location ~ \.(asp|aspx|php|cgi|sh|exe|dll)$ { return 404; }
```
- Блокируются ДО попадания в бот
- Логируются в отдельный файл

**3. Security Headers:**
```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;
```

**4. Proxy вместо alias:**
```nginx
# Было:
location /webapp/ {
    alias /var/www/BeautyAssist/webapp/;
}

# Стало:
location /webapp/ {
    proxy_pass http://127.0.0.1:8080;
    limit_req zone=webapp_limit burst=50 nodelay;
}
```
- Все запросы идут через бот
- Rate limiting для всех путей
- Бот контролирует доступ

**5. Логи:**
- `/var/log/nginx/beautyassist_access.log` - обычные запросы
- `/var/log/nginx/beautyassist_error.log` - ошибки
- `/var/log/nginx/beautyassist_blocked.log` - заблокированные атаки

---

## 🧪 Тестирование после применения

### 1. Проверка блокировки атак
```bash
# На сервере
sudo tail -f /var/log/nginx/beautyassist_blocked.log
```

В другом терминале:
```bash
curl https://mybeautyassist.ru/admin/test
curl https://mybeautyassist.ru/test.php
```

**Ожидается:** Записи в `beautyassist_blocked.log`

### 2. Проверка rate limiting
```bash
# Быстрые запросы к API
for i in {1..30}; do 
  echo "Request $i:"
  curl -s -o /dev/null -w "%{http_code}\n" https://mybeautyassist.ru/api/
  sleep 0.05
done
```

**Ожидается:** После ~15-20 запросов начнут появляться `429`

### 3. Проверка уменьшения ошибок в боте
```bash
# ДО: много BadStatusLine, BadHttpMessage
# ПОСЛЕ: ошибок должно быть значительно меньше
sudo journalctl -u beautyassist-bot --since "5 minutes ago" | grep -i "bad\|error"
```

### 4. Проверка работы WebApp
- Откройте https://mybeautyassist.ru/webapp-master/
- Откройте https://mybeautyassist.ru/webapp/
- Всё должно работать как раньше

---

## ⚠️ Возможные проблемы

### Проблема: "nginx: [emerg] unknown directive 'limit_req_zone'"

**Решение:**
```bash
# Добавить в /etc/nginx/nginx.conf в секцию http {}
sudo nano /etc/nginx/nginx.conf
```

Убедитесь, что есть:
```nginx
http {
    ...
    # Должны быть в http блоке, НЕ в server блоке
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=webapp_limit:10m rate=30r/s;
    
    include /etc/nginx/sites-enabled/*;
}
```

Или уберите `limit_req_zone` из конфига сайта и добавьте в главный конфиг.

### Проблема: "502 Bad Gateway" после применения

**Причина:** Бот ещё слушает на `0.0.0.0:8080`, а не `127.0.0.1:8080`

**Решение:**
```bash
# Сначала задеплоить изменение bot/main.py!
cd /var/www/BeautyAssist
git pull origin main
sudo systemctl restart beautyassist-bot

# Проверить, что бот слушает на 127.0.0.1
sudo netstat -tlnp | grep 8080
# Должно быть: 127.0.0.1:8080 (НЕ 0.0.0.0:8080)
```

### Проблема: WebApp не загружается после изменения

**Причина:** Кэш браузера или версия файлов

**Решение:**
```bash
# Очистить кэш браузера (Ctrl+Shift+R)
# Или проверить, что файлы загружаются:
curl -I https://mybeautyassist.ru/webapp-master/master.js
# HTTP/2 200 - хорошо
# HTTP/2 404 - плохо, проблема с путями
```

---

## 📋 Итоговый чек-лист

- [ ] **Backup:** Сохранить текущий конфиг
- [ ] **Коммит bot/main.py:** Задеплоить изменение `127.0.0.1` bind
- [ ] **Загрузить:** Новый nginx конфиг на сервер
- [ ] **Проверить:** `sudo nginx -t` → OK
- [ ] **Применить:** `sudo systemctl reload nginx`
- [ ] **Тест 1:** WebApp работает (https://mybeautyassist.ru/webapp-master/)
- [ ] **Тест 2:** Атаки блокируются (`curl .../admin/` → 404)
- [ ] **Тест 3:** Rate limiting работает (429 после burst)
- [ ] **Тест 4:** Меньше ошибок в логах бота
- [ ] **Мониторинг:** `tail -f /var/log/nginx/beautyassist_blocked.log`

---

## 🎯 Ожидаемый эффект

**До:**
```
[ERROR] BadStatusLine: b'GET /admin/login.asp HTTP/1.1'
[ERROR] BadHttpMessage: Invalid HTTP request
[ERROR] SSL handshake error
```

**После:**
```
# В логах nginx:
192.168.1.100 - [06/Dec/2024] "GET /admin/login.asp" 404 (blocked)
192.168.1.101 - [06/Dec/2024] "GET /test.php" 404 (blocked)

# В логах бота:
[INFO] Started web server on 127.0.0.1:8080
[INFO] Received valid API request from 127.0.0.1
# Нет BadStatusLine ошибок!
```

---

**Следующий шаг:** Закоммитить `bot/main.py`, задеплоить, затем обновить nginx.
