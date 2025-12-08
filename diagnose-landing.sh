#!/bin/bash
# Диагностика проблемы с лендингом

echo "=== 🔍 ДИАГНОСТИКА ПРОБЛЕМЫ С ЛЕНДИНГОМ ==="
echo ""

echo "1️⃣ Проверка файлов лендинга:"
if [ -f "/var/www/BeautyAssist/webapp/landing/index.html" ]; then
    echo "✅ index.html существует"
    ls -lh /var/www/BeautyAssist/webapp/landing/index.html
else
    echo "❌ index.html НЕ НАЙДЕН!"
fi
echo ""

echo "2️⃣ Проверка конфига nginx:"
if grep -q "alias /var/www/BeautyAssist/webapp/landing/" /etc/nginx/sites-available/beautyassist; then
    echo "✅ Новый конфиг применён (найдена строка с landing)"
else
    echo "❌ СТАРЫЙ КОНФИГ! Нужно заменить!"
fi
echo ""

echo "3️⃣ Содержимое location = / в конфиге:"
grep -A 5 "location = /" /etc/nginx/sites-available/beautyassist
echo ""

echo "4️⃣ Проверка симлинка:"
ls -la /etc/nginx/sites-enabled/ | grep beautyassist
echo ""

echo "5️⃣ Проверка синтаксиса nginx:"
sudo nginx -t
echo ""

echo "6️⃣ Тест прямого обращения к файлу:"
curl -I http://localhost/landing/index.html 2>&1 | head -n 5
echo ""

echo "7️⃣ Проверка что nginx видит конфиг:"
sudo nginx -T 2>&1 | grep -A 10 "location = /"
echo ""

echo "8️⃣ Последние ошибки nginx:"
sudo tail -5 /var/log/nginx/beautyassist_error.log
echo ""

echo "=== 🎯 РЕКОМЕНДАЦИИ ==="
echo ""
echo "Если видите 'return 301 https://t.me' в пункте 3 - конфиг НЕ обновился!"
echo "Выполните:"
echo "  sudo cp /var/www/BeautyAssist/nginx-with-landing.conf /etc/nginx/sites-available/beautyassist"
echo "  sudo nginx -t"
echo "  sudo systemctl reload nginx"
echo ""
