# 🚀 Быстрый деплой - Day 2

## Команды для VPS

```bash
# 1. Подключиться
ssh root@v2992624.hosted-by-vdsina.ru

# 2. Перейти в проект и обновить
cd /var/www/BeautyAssist
git pull origin main

# 3. Перезапустить бота
sudo systemctl restart beautyassist-bot

# 4. Проверить статус (должно быть active)
sudo systemctl status beautyassist-bot

# 5. Проверить логи
tail -50 /var/www/BeautyAssist/logs/bot.log

# 6. Убедиться что scheduler работает
tail -f /var/www/BeautyAssist/logs/bot.log | grep reminder
# Должны быть записи каждую минуту
```

## Быстрый тест

```bash
# Создать тестовый reminder в БД
psql -U beautyassist -d beautyassist

INSERT INTO reminders (
    appointment_id, 
    reminder_type, 
    scheduled_time,
    channel,
    status,
    extra_data
) VALUES (
    (SELECT id FROM appointments ORDER BY id DESC LIMIT 1),
    'cancelled_by_master',
    NOW(),
    'telegram',
    'pending',
    '{"reason": "Тест деплоя"}'
);

# Подождать 1-2 минуты - клиент должен получить уведомление

# Проверить что отправлено
SELECT 
    id, 
    reminder_type, 
    status, 
    sent_at,
    error_message
FROM reminders 
WHERE reminder_type = 'cancelled_by_master'
ORDER BY created_at DESC 
LIMIT 1;
```

## Ожидаемый результат

✅ Bot status: **active (running)**  
✅ Логи: "Reminder scheduler started"  
✅ Уведомления приходят за 1-2 минуты  
✅ Цены отображаются в appointments.html  

## Если что-то не так

```bash
# Откат на предыдущую версию
cd /var/www/BeautyAssist
git reset --hard bc676c6
sudo systemctl restart beautyassist-bot
```

## После успешного теста

📝 Заполнить TEST_PLAN_DAY2.md  
🎯 Начать Day 3: Finances Mini App
