#!/bin/bash
# 🔍 Скрипт проверки совместимости при обновлении

echo "🔍 Проверка совместимости с новой версией BeautyAssist..."
echo ""

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# 1. Проверка Git
echo "1️⃣ Проверка Git репозитория..."
if [ -d ".git" ]; then
    echo -e "${GREEN}✓${NC} Git репозиторий найден"
    
    # Проверка незакоммиченных изменений
    if ! git diff-index --quiet HEAD --; then
        echo -e "${YELLOW}⚠${NC} Есть незакоммиченные изменения!"
        echo "   Сохраните их перед обновлением: git stash"
        WARNINGS=$((WARNINGS+1))
    fi
    
    # Проверка, сколько коммитов позади
    git fetch origin main 2>/dev/null
    BEHIND=$(git rev-list HEAD..origin/main --count 2>/dev/null)
    if [ "$BEHIND" -gt 0 ]; then
        echo -e "${YELLOW}⚠${NC} Вы позади origin/main на $BEHIND коммитов"
    else
        echo -e "${GREEN}✓${NC} Актуальная версия"
    fi
else
    echo -e "${RED}✗${NC} Не Git репозиторий"
    ERRORS=$((ERRORS+1))
fi
echo ""

# 2. Проверка Python
echo "2️⃣ Проверка Python окружения..."
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC} Виртуальное окружение найдено"
    
    # Активируем venv
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
    
    # Проверяем версию Python
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    echo "   Python версия: $PYTHON_VERSION"
    
    # Проверяем наличие основных пакетов
    echo "   Проверка пакетов..."
    for package in aiogram sqlalchemy alembic aiohttp redis pydantic; do
        if python -c "import $package" 2>/dev/null; then
            echo -e "   ${GREEN}✓${NC} $package установлен"
        else
            echo -e "   ${RED}✗${NC} $package НЕ установлен"
            ERRORS=$((ERRORS+1))
        fi
    done
else
    echo -e "${RED}✗${NC} Виртуальное окружение не найдено"
    echo "   Создайте его: python -m venv venv"
    ERRORS=$((ERRORS+1))
fi
echo ""

# 3. Проверка .env файла
echo "3️⃣ Проверка .env конфигурации..."
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} Файл .env найден"
    
    # Проверяем обязательные переменные
    REQUIRED_VARS=("BOT_TOKEN" "DATABASE_URL")
    for var in "${REQUIRED_VARS[@]}"; do
        if grep -q "^$var=" .env; then
            echo -e "   ${GREEN}✓${NC} $var установлен"
        else
            echo -e "   ${RED}✗${NC} $var НЕ установлен"
            ERRORS=$((ERRORS+1))
        fi
    done
    
    # Проверяем новые переменные (могут отсутствовать)
    NEW_VARS=("REDIS_URL" "ADMIN_TELEGRAM_IDS" "LOG_LEVEL")
    for var in "${NEW_VARS[@]}"; do
        if grep -q "^$var=" .env; then
            echo -e "   ${GREEN}✓${NC} $var установлен (новая переменная)"
        else
            echo -e "   ${YELLOW}⚠${NC} $var отсутствует (добавьте после обновления)"
            WARNINGS=$((WARNINGS+1))
        fi
    done
else
    echo -e "${RED}✗${NC} Файл .env не найден"
    echo "   Создайте из примера: cp .env.example .env"
    ERRORS=$((ERRORS+1))
fi
echo ""

# 4. Проверка базы данных
echo "4️⃣ Проверка подключения к базе данных..."
if [ -f ".env" ]; then
    # Попытка подключения через Python
    python -c "
import asyncio
import sys
from database import init_db, async_session_maker
from sqlalchemy import text

async def check_db():
    try:
        await init_db()
        async with async_session_maker() as session:
            await session.execute(text('SELECT 1'))
        print('✓ Подключение к БД успешно')
        return 0
    except Exception as e:
        print(f'✗ Ошибка подключения к БД: {e}')
        return 1

sys.exit(asyncio.run(check_db()))
" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} База данных доступна"
    else
        echo -e "${RED}✗${NC} Не удалось подключиться к базе данных"
        ERRORS=$((ERRORS+1))
    fi
else
    echo -e "${YELLOW}⚠${NC} Пропуск проверки (нет .env)"
fi
echo ""

# 5. Проверка Alembic миграций
echo "5️⃣ Проверка состояния миграций..."
if command -v alembic &> /dev/null; then
    CURRENT=$(alembic current 2>/dev/null | grep -oP '(?<=\(head\)|^)[a-f0-9]+' | head -1)
    HEADS=$(alembic heads 2>/dev/null | grep -oP '^[a-f0-9]+')
    
    if [ ! -z "$CURRENT" ]; then
        echo -e "${GREEN}✓${NC} Текущая миграция: $CURRENT"
        
        if [ "$CURRENT" == "$HEADS" ]; then
            echo -e "${GREEN}✓${NC} База данных актуальна"
        else
            echo -e "${YELLOW}⚠${NC} Есть неприменённые миграции"
            echo "   После обновления выполните: alembic upgrade head"
            WARNINGS=$((WARNINGS+1))
        fi
    else
        echo -e "${YELLOW}⚠${NC} Не удалось определить текущую миграцию"
        WARNINGS=$((WARNINGS+1))
    fi
else
    echo -e "${YELLOW}⚠${NC} Alembic не найден"
    WARNINGS=$((WARNINGS+1))
fi
echo ""

# 6. Проверка Redis (новое требование)
echo "6️⃣ Проверка Redis (новое требование)..."
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✓${NC} Redis запущен и доступен"
    else
        echo -e "${RED}✗${NC} Redis установлен, но не запущен"
        echo "   Запустите: sudo systemctl start redis-server"
        ERRORS=$((ERRORS+1))
    fi
else
    echo -e "${YELLOW}⚠${NC} Redis не установлен"
    echo "   Установите для rate limiting: sudo apt install redis-server"
    WARNINGS=$((WARNINGS+1))
fi
echo ""

# 7. Проверка структуры проекта
echo "7️⃣ Проверка структуры проекта..."
REQUIRED_DIRS=("bot" "database" "services" "webapp" "alembic")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "   ${GREEN}✓${NC} $dir/"
    else
        echo -e "   ${RED}✗${NC} $dir/ не найдена"
        ERRORS=$((ERRORS+1))
    fi
done

# Проверка новых директорий (после обновления появятся)
NEW_DIRS=("bot/handlers" "bot/middlewares" "webapp/admin" "webapp/master")
echo "   Новые директории (появятся после обновления):"
for dir in "${NEW_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "   ${GREEN}✓${NC} $dir/ уже существует"
    else
        echo -e "   ${YELLOW}○${NC} $dir/ будет создана"
    fi
done
echo ""

# 8. Проверка конфликтов с новой версией
echo "8️⃣ Проверка потенциальных конфликтов..."
if [ -d ".git" ]; then
    git fetch origin main 2>/dev/null
    
    # Файлы, которые будут изменены
    CHANGED_FILES=$(git diff --name-only HEAD origin/main 2>/dev/null | wc -l)
    echo "   Файлов изменится: $CHANGED_FILES"
    
    # Проверка конфликтов в критичных файлах
    CRITICAL_FILES=("bot/main.py" "database/base.py" "bot/config.py")
    echo "   Проверка критичных файлов:"
    for file in "${CRITICAL_FILES[@]}"; do
        if git diff HEAD origin/main -- "$file" &> /dev/null; then
            DIFF_SIZE=$(git diff HEAD origin/main -- "$file" | wc -l)
            if [ "$DIFF_SIZE" -gt 0 ]; then
                echo -e "   ${YELLOW}⚠${NC} $file изменится ($DIFF_SIZE строк)"
                WARNINGS=$((WARNINGS+1))
            fi
        fi
    done
    
    # Проверка локальных изменений
    if git diff-index --quiet HEAD -- 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Нет локальных изменений"
    else
        echo -e "${YELLOW}⚠${NC} Есть локальные изменения - возможны конфликты"
        WARNINGS=$((WARNINGS+1))
    fi
fi
echo ""

# 9. Проверка свободного места
echo "9️⃣ Проверка свободного места..."
AVAILABLE_SPACE=$(df -BM . | tail -1 | awk '{print $4}' | sed 's/M//')
if [ "$AVAILABLE_SPACE" -gt 500 ]; then
    echo -e "${GREEN}✓${NC} Свободно: ${AVAILABLE_SPACE}MB"
else
    echo -e "${YELLOW}⚠${NC} Мало места: ${AVAILABLE_SPACE}MB (рекомендуется >500MB)"
    WARNINGS=$((WARNINGS+1))
fi
echo ""

# 10. Проверка прав доступа
echo "🔟 Проверка прав доступа..."
if [ -w "." ]; then
    echo -e "${GREEN}✓${NC} Есть права на запись"
else
    echo -e "${RED}✗${NC} Нет прав на запись в текущую директорию"
    ERRORS=$((ERRORS+1))
fi
echo ""

# Итоги
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ ВСЁ ОТЛИЧНО!${NC}"
    echo "   Можно безопасно обновляться."
    echo ""
    echo "Следующие шаги:"
    echo "   1. Сделайте бэкап: ./scripts/backup.sh (если есть)"
    echo "   2. Обновите код: git pull origin main"
    echo "   3. Обновите зависимости: pip install -r requirements.txt"
    echo "   4. Примените миграции: alembic upgrade head"
    echo "   5. Обновите .env (добавьте REDIS_URL, ADMIN_TELEGRAM_IDS)"
    echo "   6. Перезапустите бота"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️ МОЖНО ОБНОВЛЯТЬСЯ (есть предупреждения)${NC}"
    echo "   Ошибок: $ERRORS"
    echo "   Предупреждений: $WARNINGS"
    echo ""
    echo "   Обратите внимание на предупреждения выше!"
    echo "   Рекомендуется сделать бэкап перед обновлением."
    exit 0
else
    echo -e "${RED}❌ ЕСТЬ ПРОБЛЕМЫ!${NC}"
    echo "   Ошибок: $ERRORS"
    echo "   Предупреждений: $WARNINGS"
    echo ""
    echo "   Устраните ошибки перед обновлением!"
    echo "   См. подробности выше ☝️"
    exit 1
fi
