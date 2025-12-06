# Анализ и оптимизация финансовой системы

**Дата:** 2024-12-06  
**Статус:** ✅ Финансы работают, найдены точки для оптимизации

---

## 📊 Текущее состояние

### Реализовано:
- ✅ CRUD операции для расходов (expenses)
- ✅ Финансовая аналитика (revenue, expenses, profit, margin)
- ✅ WebApp интерфейс `/webapp-master/finances.html`
- ✅ Графики Chart.js (revenue by service, expenses by category)
- ✅ Периоды: неделя, месяц, год, произвольный
- ✅ API: 7 endpoints (analytics, CRUD expenses)
- ✅ Индекс на `expenses.master_id`

---

## 🐛 Найденные проблемы

### 1. **Отсутствует индекс на `expense_date`**
**Проблема:**
```python
# database/models/expense.py, строка 38
expense_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
# Нет index=True!
```

**Последствия:**
- Медленные запросы при фильтрации по периоду
- Full table scan при `WHERE expense_date BETWEEN start AND end`
- Замедление при росте количества расходов

**Запросы:**
```python
# expense.py:112 - get_total_by_period
Expense.expense_date >= start_date
Expense.expense_date <= end_date

# expense.py:140 - get_expenses_by_category
Expense.expense_date >= start_date
Expense.expense_date <= end_date
```

**Решение:**
```python
expense_date: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    index=True  # ← Добавить!
)
```

**Миграция:**
```sql
CREATE INDEX ix_expenses_expense_date ON expenses(expense_date);
```

---

### 2. **Композитный индекс отсутствует**
**Проблема:**
Все запросы фильтруют по `(master_id, expense_date)` одновременно, но есть только индекс на `master_id`.

**Текущие индексы:**
- ✅ `ix_expenses_master_id` (есть)
- ❌ `ix_expenses_master_id_expense_date` (нет!)

**Запросы, которые выиграют:**
```sql
-- get_by_master с фильтром по датам (используется в 3 местах)
SELECT * FROM expenses 
WHERE master_id = ? AND expense_date BETWEEN ? AND ?
ORDER BY expense_date DESC;

-- get_total_by_period
SELECT SUM(amount) FROM expenses
WHERE master_id = ? AND expense_date BETWEEN ? AND ?;

-- get_expenses_by_category
SELECT category, SUM(amount) FROM expenses
WHERE master_id = ? AND expense_date BETWEEN ? AND ?
GROUP BY category;
```

**Решение:**
```python
# database/models/expense.py
from sqlalchemy import Index

class Expense(Base):
    __tablename__ = "expenses"
    
    # ... существующие поля ...
    
    __table_args__ = (
        Index('ix_expenses_master_date', 'master_id', 'expense_date'),
    )
```

**Миграция:**
```sql
CREATE INDEX ix_expenses_master_date ON expenses(master_id, expense_date);
```

**Эффект:**
- Ускорение запросов по периоду в 10-100 раз (при большом объёме данных)
- Postgres сможет использовать index-only scan

---

### 3. **N+1 проблема в get_financial_analytics**
**Проблема:**
```python
# bot/handlers/api.py:1263-1280
async def get_financial_analytics(request):
    # 1. Запрос завершённых записей
    completed_appointments = await arepo.get_completed_by_period(...)  # Query 1
    
    # 2. Цикл по записям для подсчёта по услугам
    revenue_by_service = {}
    for app in completed_appointments:
        if app.service_id:
            service = await srepo.get_by_id(app.service_id)  # Query 2, 3, 4, ...
            # N дополнительных запросов!
```

**Последствия:**
- Если 50 записей → 51 запрос к БД
- Если 100 записей → 101 запрос
- Медленный API response (100-500ms вместо 10-50ms)

**Решение 1: Prefetch services**
```python
# Загрузить все services одним запросом
service_ids = {app.service_id for app in completed_appointments if app.service_id}
services = await srepo.get_by_ids(list(service_ids))  # Один запрос
service_map = {s.id: s for s in services}

# Использовать закэшированные данные
for app in completed_appointments:
    if app.service_id and app.service_id in service_map:
        service = service_map[app.service_id]
        # ...
```

**Решение 2: JOIN в SQL**
```python
# appointment.py - добавить метод
async def get_completed_with_services(master_id, start_date, end_date):
    stmt = (
        select(Appointment, Service)
        .join(Service, Appointment.service_id == Service.id)
        .where(...)
    )
    result = await self.session.execute(stmt)
    return result.all()
```

**Эффект:**
- 51 запрос → 2 запроса
- 500ms → 50ms response time

---

### 4. **Отсутствует кэширование аналитики**
**Проблема:**
При каждом открытии страницы finances.html выполняются тяжёлые запросы:
- Подсчёт выручки (JOIN с appointments + services)
- Подсчёт расходов (GROUP BY category)
- Загрузка списка расходов

Если мастер часто смотрит статистику → лишняя нагрузка на БД.

**Решение: Redis cache**
```python
# services/analytics_cache.py
import redis.asyncio as redis
import json
from datetime import timedelta

redis_client = redis.Redis(...)

async def get_or_compute_financial_analytics(master_id, period):
    cache_key = f"analytics:financial:{master_id}:{period}"
    
    # Попытка взять из кэша
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Вычислить
    analytics = await compute_financial_analytics(master_id, period)
    
    # Сохранить в кэш на 5 минут
    await redis_client.setex(
        cache_key,
        timedelta(minutes=5),
        json.dumps(analytics)
    )
    
    return analytics
```

**Инвалидация кэша:**
- При создании/обновлении/удалении expense
- При завершении appointment (payment_received)

**Эффект:**
- Первый запрос: 200ms
- Последующие 5 минут: 5ms
- Снижение нагрузки на БД на 80-90%

---

### 5. **Нет пагинации для списка расходов**
**Проблема:**
```python
# bot/handlers/api.py:1393
expenses = await erepo.get_by_master(
    master_id=master.id,
    start_date=start_date,
    end_date=end_date
)
# Возвращает ВСЕ расходы за период без лимита!
```

**Последствия:**
- Если мастер добавил 1000 расходов за год → API вернёт все 1000
- Большой JSON response (100+ KB)
- Медленная загрузка страницы
- Браузер может зависнуть при рендеринге

**Решение:**
```python
# database/repositories/expense.py
async def get_by_master(
    self,
    master_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    category: Optional[str] = None,
    limit: int = 100,  # ← Добавить
    offset: int = 0    # ← Добавить
) -> tuple[List[Expense], int]:  # ← Вернуть total count
    # ... фильтры ...
    
    # Подсчёт total
    count_stmt = select(func.count()).where(and_(*conditions))
    total = await self.session.scalar(count_stmt)
    
    # Запрос с пагинацией
    stmt = (
        select(Expense)
        .where(and_(*conditions))
        .order_by(Expense.expense_date.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await self.session.execute(stmt)
    return list(result.scalars().all()), total
```

**API:**
```python
# GET /api/master/expenses?mid=123&limit=50&offset=0
{
  "expenses": [...],  # 50 элементов
  "total": 234,       # Всего записей
  "has_more": true    # Есть ли ещё
}
```

**Frontend (finances.js):**
```javascript
let currentPage = 0;
const PAGE_SIZE = 50;

async function loadExpenses() {
  const data = await api(
    `/api/master/expenses?mid=${mid}&limit=${PAGE_SIZE}&offset=${currentPage * PAGE_SIZE}`
  );
  renderExpenses(data.expenses);
  if (data.has_more) {
    showLoadMoreButton();
  }
}
```

**Эффект:**
- Первый запрос: 50 записей вместо 1000
- 10 KB JSON вместо 200 KB
- Быстрая загрузка страницы

---

### 6. **Отсутствует валидация категорий**
**Проблема:**
```python
# bot/handlers/api.py:1418
category = data.get("category")
# Нет проверки, что category допустимая!
```

**Последствия:**
- Можно создать expense с `category="хрень"`, `category="zzz"`
- Графики сломаются (незнакомые категории)
- Несогласованность данных

**Решение:**
```python
# database/models/expense.py
import enum

class ExpenseCategory(str, enum.Enum):
    MATERIALS = "materials"
    RENT = "rent"
    ADVERTISING = "advertising"
    TRANSPORT = "transport"
    EDUCATION = "education"
    EQUIPMENT = "equipment"
    OTHER = "other"

class Expense(Base):
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Category: materials, rent, advertising, etc."
    )
    
    # Добавить constraint
    __table_args__ = (
        Index('ix_expenses_master_date', 'master_id', 'expense_date'),
        CheckConstraint(
            category.in_([c.value for c in ExpenseCategory]),
            name='check_expense_category'
        ),
    )
```

**API валидация:**
```python
# bot/handlers/api.py
async def create_expense(request):
    category = data.get("category")
    
    # Валидация
    try:
        ExpenseCategory(category)
    except ValueError:
        return web.json_response({
            "error": f"invalid category. Allowed: {[c.value for c in ExpenseCategory]}"
        }, status=400)
```

**Эффект:**
- Гарантия согласованности данных
- Защита от опечаток
- Предсказуемое поведение графиков

---

### 7. **Нет обработки часовых поясов**
**Проблема:**
```python
# bot/handlers/api.py:1376
start_date = datetime.fromisoformat(start_date_iso)
end_date = datetime.fromisoformat(end_date_iso)
# Нет конвертации в UTC!
```

**Последствия:**
- Клиент отправляет "2024-12-06T10:00:00+03:00" (MSK)
- Сервер интерпретирует как naive datetime
- Сравнение с `expense_date` (timezone-aware) может быть неправильным

**Решение:**
```python
from datetime import datetime, timezone

# Всегда конвертировать в UTC
start_date = datetime.fromisoformat(start_date_iso).astimezone(timezone.utc)
end_date = datetime.fromisoformat(end_date_iso).astimezone(timezone.utc)

# Или использовать pendulum
import pendulum
start_date = pendulum.parse(start_date_iso).in_timezone('UTC')
```

**Эффект:**
- Корректная работа для мастеров в разных часовых поясах
- Нет путаницы с датами

---

### 8. **Отсутствует bulk delete**
**Проблема:**
Нет возможности удалить несколько расходов одновременно.

**Пользовательский сценарий:**
- Мастер ошибочно добавил 20 расходов
- Приходится удалять по одному (20 кликов + 20 API запросов)

**Решение:**
```python
# database/repositories/expense.py
async def delete_many(self, expense_ids: List[int], master_id: int) -> int:
    """Delete multiple expenses. Returns count deleted."""
    stmt = delete(Expense).where(
        and_(
            Expense.id.in_(expense_ids),
            Expense.master_id == master_id  # Security check
        )
    )
    result = await self.session.execute(stmt)
    await self.session.flush()
    return result.rowcount

# API
# POST /api/master/expenses/bulk-delete
{
  "mid": 123,
  "expense_ids": [45, 46, 47, 48]
}
```

**Frontend:**
```javascript
// Чекбоксы для выбора нескольких расходов
// Кнопка "Удалить выбранные"
```

**Эффект:**
- Удобство использования
- 20 запросов → 1 запрос

---

## 🚀 План оптимизации (приоритеты)

### Приоритет 1: Критично для производительности (30 минут)
1. ✅ **Добавить индекс на `expense_date`** (5 мин)
   - Миграция + тест
   
2. ✅ **Добавить композитный индекс `(master_id, expense_date)`** (5 мин)
   - Миграция + тест

3. ✅ **Исправить N+1 в get_financial_analytics** (20 мин)
   - Prefetch services
   - Тест производительности

### Приоритет 2: Важно для масштабирования (40 минут)
4. ✅ **Добавить пагинацию для expenses** (25 мин)
   - Обновить repository
   - Обновить API
   - Обновить frontend (кнопка "Загрузить ещё")

5. ✅ **Валидация категорий** (15 мин)
   - Enum + constraint
   - API validation

### Приоритет 3: Хорошо иметь (опционально, 60 минут)
6. ⏳ **Redis кэширование аналитики** (30 мин)
   - Требует установки Redis
   - Cache + invalidation logic

7. ⏳ **Bulk delete** (20 мин)
   - API + frontend

8. ⏳ **Timezone handling** (10 мин)
   - Pendulum library
   - UTC conversion

---

## 📝 Итоговая оценка

**Текущая производительность:**
- ✅ Работает корректно
- ⚠️ Медленно при большом объёме данных (1000+ records)
- ⚠️ N+1 проблема в аналитике

**После оптимизации (Приоритет 1+2):**
- ✅ В 10-50 раз быстрее запросы по периоду
- ✅ N+1 исправлен (51 запрос → 2)
- ✅ Пагинация защищает от перегрузки
- ✅ Валидация данных

**Время работы:** ~70 минут на Приоритет 1 + 2

---

**Следующий шаг:** Начать с Приоритета 1 (индексы + N+1)?
