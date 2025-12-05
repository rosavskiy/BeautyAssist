#!/bin/bash
# 🔧 Безопасная синхронизация миграций

set -e  # Остановка при ошибках

# Активируем виртуальное окружение
source venv/bin/activate

echo "🔍 Проверка состояния миграций..."
echo ""

# Проверяем текущую версию
CURRENT=$(alembic current 2>&1 | grep -oP '(?<=\(head\)|^)[a-f0-9]+' | head -1 || echo "none")
echo "Текущая версия в БД: $CURRENT"

# Проверяем наличие таблицы masters
echo ""
echo "🗄️ Проверка существующих таблиц..."
psql $DATABASE_URL -c "\dt" 2>/dev/null || echo "Не удалось подключиться через psql, используем Python..."

# Используем Python для проверки
python3 << 'PYEOF'
import asyncio
from sqlalchemy import text, inspect
from database import engine

async def check_tables():
    async with engine.connect() as conn:
        # Получаем список таблиц
        result = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """))
        tables = [row[0] for row in result]
        
        print(f"\nНайдено таблиц: {len(tables)}")
        print("Таблицы в БД:", ", ".join(tables))
        
        # Проверяем ключевые таблицы
        key_tables = ['masters', 'clients', 'services', 'appointments']
        existing = [t for t in key_tables if t in tables]
        
        if existing:
            print(f"\n✅ Существующие таблицы: {', '.join(existing)}")
            print("➡️  База данных УЖЕ инициализирована")
            return True
        else:
            print("\n⚠️  Основные таблицы не найдены")
            print("➡️  Это новая база данных")
            return False

try:
    has_tables = asyncio.run(check_tables())
except Exception as e:
    print(f"\n❌ Ошибка проверки: {e}")
    has_tables = False

if has_tables:
    print("\n" + "="*50)
    print("🔧 СТРАТЕГИЯ: Синхронизация с существующей БД")
    print("="*50)
else:
    print("\n" + "="*50)
    print("🆕 СТРАТЕГИЯ: Чистая инициализация")
    print("="*50)
PYEOF

echo ""
read -p "Продолжить? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Отменено"
    exit 1
fi

echo ""
echo "⚙️ Применяем исправление..."

# Если есть таблицы - синхронизируем
# Stamp на версию ПЕРЕД проблемной миграцией
echo "📌 Помечаем базу как находящуюся на версии 0b08f72a12d1..."
alembic stamp 0b08f72a12d1

echo ""
echo "⬆️ Применяем новые миграции..."
alembic upgrade head

echo ""
echo "✅ Проверка результата:"
alembic current

echo ""
echo "🎉 Миграции синхронизированы!"
echo ""
echo "📋 Применённые миграции:"
alembic history | head -20
