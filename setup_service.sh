#!/bin/bash
set -e

echo "🚀 Настройка и запуск бота..."
echo ""

# Копируем service файл
echo "📋 Копируем systemd service..."
sudo cp beautyassist.service /etc/systemd/system/

# Перезагружаем systemd
echo "🔄 Перезагружаем systemd daemon..."
sudo systemctl daemon-reload

# Включаем автозапуск
echo "✅ Включаем автозапуск..."
sudo systemctl enable beautyassist

# Запускаем бота
echo "▶️  Запускаем бота..."
sudo systemctl start beautyassist

# Ждём 3 секунды
sleep 3

# Проверяем статус
echo ""
echo "📊 Статус сервиса:"
sudo systemctl status beautyassist --no-pager

echo ""
echo "📝 Последние логи:"
sudo journalctl -u beautyassist -n 20 --no-pager

echo ""
echo "🎉 Готово!"
echo ""
echo "Полезные команды:"
echo "  sudo systemctl status beautyassist    - статус бота"
echo "  sudo systemctl restart beautyassist   - перезапуск бота"
echo "  sudo systemctl stop beautyassist      - остановка бота"
echo "  sudo journalctl -u beautyassist -f    - логи в реальном времени"
