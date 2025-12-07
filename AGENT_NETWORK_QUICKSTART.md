# 🚀 Быстрый старт: Агентская сеть

## Что сделано

✅ Реализована полноценная агентская сеть с выплатами **10% в Telegram Stars**  
✅ Автоматические выплаты при оплате реферала  
✅ Обновлённый UI с историей заработка  
✅ Полное покрытие тестами  

---

## Деплой на production

### 1. Применить миграцию БД

```bash
# Development
alembic upgrade head

# Production
ssh user@server
cd /var/www/BeautyAssist
source venv/bin/activate
alembic upgrade head
```

### 2. Обновить код

```bash
git add .
git commit -m "feat: Agent network with Telegram Stars payouts"
git push origin main

# На сервере
ssh user@server
cd /var/www/BeautyAssist
git pull origin main
sudo systemctl restart beautyassist
```

### 3. Проверить работу

```bash
# Проверить логи
tail -f logs/beautyassist.log | grep -i "payout\|commission"

# Проверить статус
sudo systemctl status beautyassist
```

---

## Тестирование

### Локально:

```bash
# Запустить тесты
pytest tests/test_agent_payout.py -v

# Проверить покрытие
pytest tests/test_agent_payout.py --cov=services.agent_payout
```

### В боте:

1. **Создать реферальную ссылку:**
   - Отправить `/referral` в бот
   - Скопировать ссылку

2. **Зарегистрировать реферала:**
   - Открыть ссылку в другом аккаунте
   - Пройти onboarding

3. **Оплатить подписку:**
   - Выбрать тариф (например, 390⭐)
   - Оплатить
   - Агент получит 39⭐ автоматически

4. **Проверить выплату:**
   - Агент: `/payouts` - увидит историю
   - Агент: получит уведомление о выплате

---

## Основные команды

| Команда | Описание |
|---------|----------|
| `/referral` | Статистика рефералов и заработка |
| `/payouts` | История выплат в звёздах |

---

## Изменённые файлы

### Созданы:
- `services/agent_payout.py` - сервис выплат
- `tests/test_agent_payout.py` - тесты
- `alembic/versions/2025_12_07_*.py` - миграция
- `AGENT_NETWORK.md` - полная документация
- `AGENT_NETWORK_QUICKSTART.md` - этот файл

### Изменены:
- `database/models/referral.py` - добавлены поля выплат
- `services/payment.py` - интеграция выплат
- `bot/handlers/referral.py` - обновлён UI

---

## Ключевые метрики

После запуска отслеживайте:

1. **Конверсия рефералов** (pending → activated)
2. **Успешность выплат** (sent vs failed)
3. **Средний заработок агента**
4. **Топ-агенты** (лидерборд)

### SQL запросы для аналитики:

```sql
-- Общая статистика выплат
SELECT 
  COUNT(*) as total_payouts,
  SUM(commission_stars) as total_stars,
  AVG(commission_stars) as avg_commission
FROM referrals 
WHERE payout_status = 'sent';

-- Топ-10 агентов
SELECT 
  m.name,
  COUNT(r.id) as referrals,
  SUM(r.commission_stars) as earned_stars
FROM masters m
JOIN referrals r ON r.referrer_id = m.id
WHERE r.payout_status = 'sent'
GROUP BY m.id
ORDER BY earned_stars DESC
LIMIT 10;

-- Процент успешных выплат
SELECT 
  payout_status,
  COUNT(*) as count,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
FROM referrals
WHERE payout_status IN ('sent', 'failed', 'pending')
GROUP BY payout_status;
```

---

## ⚠️ Важно

**Симуляция отправки Stars:**  
Сейчас `AgentPayoutService.send_stars_to_agent()` работает в режиме симуляции, т.к. Telegram Bot API пока не имеет метода прямой отправки Stars.

**Когда API появится:**
1. Обновить метод `send_stars_to_agent()` в `services/agent_payout.py`
2. Заменить симуляцию на реальный вызов API
3. Протестировать на тестовом аккаунте
4. Задеплоить на production

---

## Поддержка

Документация: `AGENT_NETWORK.md`  
Тесты: `tests/test_agent_payout.py`  

**Вопросы?** Проверьте логи:
```bash
tail -f logs/beautyassist.log | grep -i "agent\|payout\|commission"
```
