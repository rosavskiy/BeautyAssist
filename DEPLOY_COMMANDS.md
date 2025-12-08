# 🚀 Шпаргалка: Деплой лендинга (копируй-вставляй)

## 📦 Локально (Windows PowerShell)

```powershell
# Перейти в проект
cd d:\Projects\BeautyAssist

# Проверить что изменилось
git status

# Добавить все файлы лендинга
git add webapp/landing/
git add nginx-with-landing.conf
git add DEPLOY_LANDING.md
git add LANDING_CHECKLIST.md

# Закоммитить
git commit -m "feat: add lavender-themed landing page with SEO optimization"

# Запушить на GitHub
git push origin main
```

---

## 🖥️ На сервере (SSH)

```bash
# 1. Подключиться к серверу
ssh root@YOUR_SERVER_IP

# 2. Перейти в проект
cd /var/www/BeautyAssist

# 3. Остановить бот (на всякий случай)
sudo systemctl stop beautyassist

# 4. Скачать обновления
git pull origin main

# 5. Обновить nginx конфиг
sudo cp nginx-with-landing.conf /etc/nginx/sites-available/beautyassist

# 6. Проверить конфиг (ВАЖНО!)
sudo nginx -t

# Если всё OK, продолжаем:

# 7. Перезагрузить nginx
sudo systemctl reload nginx

# 8. Запустить бот обратно
sudo systemctl start beautyassist

# 9. Проверить что всё работает
sudo systemctl status beautyassist
sudo systemctl status nginx

# 10. Проверить лендинг
curl -I https://mybeautyassist.ru/
```

---

## ✅ Быстрая проверка

```bash
# Лендинг открывается?
curl -I https://mybeautyassist.ru/
# Должно быть: HTTP/2 200

# Редирект на бот работает?
curl -I https://mybeautyassist.ru/bot
# Должно быть: HTTP/2 301
# Location: https://t.me/mybeautyassist_bot

# Все файлы на месте?
ls -la /var/www/BeautyAssist/webapp/landing/
# Должны быть: index.html, styles.css, script.js, sitemap.xml, robots.txt
```

---

## 🔧 Если что-то не работает

```bash
# Посмотреть логи nginx
sudo tail -f /var/log/nginx/beautyassist_error.log

# Посмотреть логи бота
sudo journalctl -u beautyassist -n 50 --no-pager

# Проверить права на файлы
sudo chown -R www-data:www-data /var/www/BeautyAssist/webapp/landing/
sudo chmod -R 755 /var/www/BeautyAssist/webapp/landing/

# Перезапустить nginx
sudo systemctl restart nginx

# Перезапустить бот
sudo systemctl restart beautyassist
```

---

## 📊 Настроить Яндекс.Метрику (потом)

```bash
# 1. Создать счётчик на https://metrika.yandex.ru
# 2. Скопировать ID (например: 12345678)
# 3. На сервере:

nano /var/www/BeautyAssist/webapp/landing/script.js

# Найти строку (в самом начале файла):
const YANDEX_METRIKA_ID = 'YOUR_METRIKA_ID';

# Заменить на ваш ID:
const YANDEX_METRIKA_ID = '12345678';

# Сохранить: Ctrl+O, Enter, Ctrl+X

# Готово! Метрика начнёт собирать данные
```

---

## 🌐 Добавить в Яндекс.Вебмастер (для SEO)

```bash
1. Зайти: https://webmaster.yandex.ru
2. Добавить сайт: mybeautyassist.ru
3. Подтвердить права (через HTML-файл или DNS)
4. Добавить Sitemap: https://mybeautyassist.ru/landing/sitemap.xml
5. Подождать 2-7 дней для индексации

# Проверить индексацию в Яндекс:
# Поиск: site:mybeautyassist.ru
```

---

## 🎯 Проверить в браузере

1. Откройте: https://mybeautyassist.ru/
   - ✅ Виден лендинг с лавандовым дизайном
   - ✅ Кнопки "Начать бесплатно" работают
   - ✅ Цены правильные (790₽/мес)

2. Откройте: https://mybeautyassist.ru/bot
   - ✅ Перенаправляет на t.me/mybeautyassist_bot

3. Откройте DevTools (F12) → Console
   - ✅ Нет ошибок (красных текстов)
   - ✅ Виден лог: "[BeautyAssist Landing] Initialized successfully"

4. Проверьте на телефоне
   - ✅ Всё адаптировано под мобильный

---

## 🎉 Готово!

Лендинг задеплоен на https://mybeautyassist.ru/ ✅

**Что дальше:**
- См. `LANDING_CHECKLIST.md` для полной проверки
- См. `IMAGES_GUIDE.md` для создания картинок
- См. `MARKETING_GUIDE.md` для привлечения трафика
