"""Скрипт для исправления тестов"""
import re

def fix_test_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Исправляем создание Master - добавляем referral_code
    content = re.sub(
        r'Master\(\s*telegram_id=(\d+),\s*phone="([^"]+)",\s*name="([^"]+)"',
        lambda m: f'Master(telegram_id={m.group(1)}, phone="{m.group(2)}", name="{m.group(3)}", referral_code="REF{m.group(1)[-6:]}"',
        content
    )
    
    # Заменяем plan_type на plan
    content = content.replace('plan_type=', 'plan=')
    content = content.replace('.plan_type', '.plan')
    
    # Убираем trial_used
    content = re.sub(r',\s*trial_used=\w+', '', content)
    
    # Убираем reminder_3d_sent и reminder_1d_sent
    content = re.sub(r',\s*reminder_\dd_sent=\w+', '', content)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Fixed {filename}")

# Исправляем все тестовые файлы
for filename in [
    'tests/test_subscriptions.py',
    'tests/test_promo_codes.py',
    'tests/test_payment.py',
    'tests/test_subscription_monitor.py'
]:
    try:
        fix_test_file(filename)
    except Exception as e:
        print(f"Error fixing {filename}: {e}")
