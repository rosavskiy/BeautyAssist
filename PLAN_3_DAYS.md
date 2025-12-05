# 📋 План работы на 3 дня (6-8 декабря 2025)

**Дата составления:** 5 декабря 2025  
**Основа:** SPRINT_7_PLAN.md  
**Цель:** Завершить Admin Analytics и начать миграцию в Mini App

---

## 📊 Текущее состояние проекта

### ✅ Завершено
- **Спринт 1-2**: Рефакторинг архитектуры (модульность, middleware, логирование)
- **Спринт 3**: Оптимизация БД (индексы, производительность)
- **Спринт 4**: Unit-тесты (61+ тестов, ~70% coverage)
- **Спринт 5**: Admin Panel (dashboard, рассылки, управление мастерами)
- **Спринт 6**: Монетизация (подписки, промокоды, финансовая аналитика)
- **Спринт 7.1**: Реферальная программа (✅ полностью реализована)

### 🎯 Текущий приоритет (Sprint 7)
**Основные блоки:**
1. ✅ Реферальная программа (завершено)
2. 🔥 **Admin Analytics** - расширенная аналитика (retention, cohorts, funnel)
3. 🌐 **Миграция в Mini App** - современный UX для управления услугами

---

## 🗓️ План на 3 дня

### День 1 (6 декабря) - Analytics Backend + Admin Dashboard

#### Утро (4 часа)
**Задача:** Создать AnalyticsService с метриками retention, cohorts, funnel

**Файлы:**
- `services/analytics.py` - новый сервис
  - Метод `get_retention_report()` - Day 1/7/30 retention
  - Метод `get_cohort_analysis()` - retention по неделям регистрации
  - Метод `get_funnel_conversion()` - воронка онбординга
  - Метод `get_growth_metrics()` - DAU/WAU/MAU

**SQL запросы:**
```python
# Retention: процент активных пользователей через N дней после регистрации
# Cohorts: группировка по неделям, расчёт retention для каждой когорты
# Funnel: зарегистрировались → онбординг → создали услугу → получили запись → оплатили
# Growth: подсчёт уникальных активных пользователей за период
```

**Индексы для оптимизации:**
- `masters.created_at` (для cohort analysis)
- `masters.last_active_at` (для retention)
- `masters.onboarded` (для funnel)

**Критерии готовности:**
- ✅ Все 4 метода реализованы
- ✅ SQL запросы оптимизированы (EXPLAIN ANALYZE)
- ✅ Type hints и docstrings
- ✅ Логирование ошибок

#### День (3 часа)
**Задача:** API endpoints для аналитики

**Файлы:**
- `bot/handlers/api.py` - 4 новых endpoint'а:
  - `GET /api/admin/analytics/retention`
  - `GET /api/admin/analytics/cohorts`
  - `GET /api/admin/analytics/funnel`
  - `GET /api/admin/analytics/growth`

**Защита:**
- Middleware проверки админа (уже есть в `AdminOnlyMiddleware`)
- Валидация query параметров (start_date, end_date, period)

**Формат ответа:**
```json
{
  "retention": {
    "day1": 70.5,
    "day7": 52.3,
    "day30": 38.1
  },
  "cohorts": [
    {"week": "2025-W48", "registered": 15, "day7": 80.0, "day30": 53.3}
  ],
  "funnel": {
    "registered": 100,
    "onboarded": 85,
    "first_service": 72,
    "first_booking": 58,
    "paid": 45
  },
  "growth": {
    "dau": 234,
    "wau": 1523,
    "mau": 4891,
    "growth_rate": 12.5
  }
}
```

#### Вечер (3 часа)
**Задача:** Unit-тесты для AnalyticsService

**Файлы:**
- `tests/test_analytics.py` - минимум 8 тестов:
  - `test_retention_calculation` - корректный расчёт retention
  - `test_retention_empty_data` - пустое состояние
  - `test_cohort_grouping` - группировка по неделям
  - `test_cohort_retention_by_week` - retention для каждой когорты
  - `test_funnel_conversion` - расчёт воронки
  - `test_growth_metrics_dau` - DAU подсчёт
  - `test_growth_metrics_mau` - MAU подсчёт
  - `test_analytics_with_filters` - фильтры по датам

**Coverage цель:** >80% для `services/analytics.py`

**Итог дня 1:**
- ✅ Backend аналитики готов
- ✅ API endpoints работают
- ✅ Тесты покрывают основные сценарии

---

### День 2 (7 декабря) - Admin Dashboard (Mini App)

#### Утро (4 часа)
**Задача:** Создать HTML структуру Admin Dashboard

**Создать новую папку:**
- `webapp/admin/` - новая папка для админ-интерфейса

**Файлы:**
- `webapp/admin/analytics.html` - главная страница аналитики
  - Навигация: 4 таба (Overview, Retention, Cohorts, Funnel)
  - Карточки метрик (MRR, DAU, MAU, Conversion, Churn)
  - Контейнеры для графиков (canvas элементы)
  - Фильтры (date range picker)

**Структура:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Admin Analytics - BeautyAssist</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="analytics.css">
</head>
<body>
    <div class="analytics-container">
        <!-- Navigation tabs -->
        <nav class="tabs">
            <button class="tab active" data-tab="overview">Overview</button>
            <button class="tab" data-tab="retention">Retention</button>
            <button class="tab" data-tab="cohorts">Cohorts</button>
            <button class="tab" data-tab="funnel">Funnel</button>
        </nav>

        <!-- Overview tab -->
        <section id="overview" class="tab-content active">
            <div class="metrics-grid">
                <div class="metric-card">
                    <h3>MRR</h3>
                    <p class="value" id="mrr-value">₽0</p>
                    <span class="change positive" id="mrr-change">+0%</span>
                </div>
                <!-- Ещё 5 карточек: DAU, MAU, Conversion, Churn, LTV -->
            </div>
            <canvas id="growth-chart"></canvas>
        </section>

        <!-- Retention tab -->
        <section id="retention" class="tab-content">
            <canvas id="retention-chart"></canvas>
        </section>

        <!-- Cohorts tab -->
        <section id="cohorts" class="tab-content">
            <div id="cohort-table"></div>
        </section>

        <!-- Funnel tab -->
        <section id="funnel" class="tab-content">
            <canvas id="funnel-chart"></canvas>
        </section>
    </div>
    <script src="analytics.js"></script>
</body>
</html>
```

#### День (3 часа)
**Задача:** JavaScript логика и интеграция с Chart.js

**Файлы:**
- `webapp/admin/analytics.js` - логика дашборда
  - Инициализация Telegram WebApp
  - Проверка админских прав (через initData)
  - AJAX запросы к API endpoints
  - Рендеринг графиков (Chart.js)
  - Переключение табов
  - Обновление карточек метрик

**Типы графиков:**
- **Growth chart**: Line chart (DAU/WAU/MAU за последние 30 дней)
- **Retention chart**: Bar chart (Day 1/7/30 retention)
- **Cohort table**: HTML таблица с color gradient (heat map)
- **Funnel chart**: Funnel chart или Horizontal Bar chart

**Пример кода:**
```javascript
// Fetch retention data
async function loadRetentionData() {
    const response = await fetch('/api/admin/analytics/retention', {
        headers: {
            'Authorization': `tma ${Telegram.WebApp.initData}`
        }
    });
    const data = await response.json();
    renderRetentionChart(data);
}

// Render Chart.js
function renderRetentionChart(data) {
    const ctx = document.getElementById('retention-chart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Day 1', 'Day 7', 'Day 30'],
            datasets: [{
                label: 'Retention %',
                data: [data.day1, data.day7, data.day30],
                backgroundColor: ['#4CAF50', '#FF9800', '#F44336']
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
}
```

#### Вечер (3 часа)
**Задача:** CSS стилизация и адаптивность

**Файлы:**
- `webapp/admin/analytics.css` - стили дашборда
  - Тёмная тема (Telegram-style)
  - Адаптивная сетка (grid layout)
  - Карточки с тенями и hover эффектами
  - Табы с активным состоянием
  - Responsive design (мобильные устройства)

**Ключевые элементы:**
```css
.analytics-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    background: var(--tg-theme-bg-color);
    color: var(--tg-theme-text-color);
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
}

.metric-card {
    background: var(--tg-theme-secondary-bg-color);
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s;
}

.metric-card:hover {
    transform: translateY(-4px);
}
```

**Итог дня 2:**
- ✅ Admin Dashboard готов
- ✅ Графики работают (Chart.js)
- ✅ Адаптивный дизайн
- ✅ Интеграция с Telegram WebApp

---

### День 3 (8 декабря) - Миграция: Управление услугами в Mini App

#### Утро (4 часа)
**Задача:** CRUD интерфейс для услуг в Mini App

**Файлы:**
- `webapp/master/services.html` - новая страница
  - Список всех услуг мастера (таблица)
  - Кнопки: "Добавить услугу", "Редактировать", "Удалить"
  - Модальное окно для создания/редактирования
  - Подтверждение удаления

**Структура:**
```html
<div class="services-container">
    <header>
        <h1>Мои услуги</h1>
        <button id="add-service-btn" class="btn-primary">+ Добавить услугу</button>
    </header>

    <div class="services-list" id="services-list">
        <!-- Динамически загружаемый список -->
    </div>

    <!-- Modal for create/edit -->
    <div id="service-modal" class="modal">
        <div class="modal-content">
            <h2 id="modal-title">Добавить услугу</h2>
            <form id="service-form">
                <input type="text" id="service-name" placeholder="Название услуги" required>
                <input type="number" id="service-price" placeholder="Цена (₽)" required>
                <input type="number" id="service-duration" placeholder="Длительность (мин)" required>
                <textarea id="service-description" placeholder="Описание (опционально)"></textarea>
                <div class="form-actions">
                    <button type="submit" class="btn-primary">Сохранить</button>
                    <button type="button" class="btn-cancel" id="cancel-btn">Отмена</button>
                </div>
            </form>
        </div>
    </div>
</div>
```

**JavaScript логика:**
- `webapp/master/services.js`:
  - Загрузка списка услуг (`GET /api/services`)
  - Создание услуги (`POST /api/services`)
  - Обновление услуги (`PUT /api/services/{id}`)
  - Удаление услуги (`DELETE /api/services/{id}`)
  - Открытие/закрытие модального окна
  - Валидация формы

#### День (3 часа)
**Задача:** API endpoints для CRUD операций

**Файлы:**
- `bot/handlers/api.py` - добавить endpoints:
  - `GET /api/services` - список услуг мастера
  - `POST /api/services` - создание услуги
  - `PUT /api/services/{id}` - обновление услуги
  - `DELETE /api/services/{id}` - удаление услуги

**Защита:**
- Проверка `initData` (Telegram WebApp signature)
- Валидация: мастер может редактировать только свои услуги

**Пример endpoint:**
```python
@routes.get('/api/services')
async def get_services(request):
    """Get all services for master."""
    # Validate Telegram WebApp data
    init_data = request.headers.get('Authorization', '').replace('tma ', '')
    telegram_id = validate_init_data(init_data)
    
    # Get master
    async with get_db_session() as session:
        master_repo = MasterRepository(session)
        master = await master_repo.get_by_telegram_id(telegram_id)
        
        # Get services
        service_repo = ServiceRepository(session)
        services = await service_repo.get_by_master_id(master.id)
        
        return web.json_response([
            {
                'id': s.id,
                'name': s.name,
                'price': s.price,
                'duration': s.duration,
                'description': s.description
            }
            for s in services
        ])
```

#### Вечер (3 часа)
**Задача:** Рефакторинг бот-хендлера и тестирование

**Файлы:**
- `bot/handlers/master.py` - обновить:
  - Удалить FSM `AddServiceState` (больше не нужен)
  - Упростить `/services` команду → показывает кнопку "Открыть Mini App"
  - Добавить inline-кнопку с WebApp URL

**Изменения:**
```python
@router.message(Command("services"))
async def cmd_services(message: Message):
    """Show services management (now via WebApp)."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Управление услугами",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/master/services.html")
        )],
        [InlineKeyboardButton(text="« Назад", callback_data="back_to_menu")]
    ])
    
    await message.answer(
        "🛠 Управление услугами теперь доступно через удобный интерфейс Mini App!\n\n"
        "Здесь вы можете:\n"
        "• Просмотреть все услуги\n"
        "• Добавить новую услугу\n"
        "• Редактировать существующие\n"
        "• Удалить услугу",
        reply_markup=keyboard
    )
```

**Тестирование:**
- Ручное тестирование в Telegram (Desktop + Mobile)
- Проверка всех CRUD операций
- Проверка валидации (пустые поля, отрицательные числа)
- Проверка модального окна (открытие/закрытие)

**Итог дня 3:**
- ✅ Управление услугами мигрировано в Mini App
- ✅ Старый FSM-интерфейс удалён
- ✅ API endpoints работают
- ✅ UI протестирован на Desktop и Mobile

---

## 📊 Ожидаемые результаты (к концу 3 дней)

### Созданные файлы:
1. `services/analytics.py` - аналитический сервис
2. `tests/test_analytics.py` - тесты для аналитики
3. `webapp/admin/analytics.html` - Admin Dashboard
4. `webapp/admin/analytics.js` - логика дашборда
5. `webapp/admin/analytics.css` - стили дашборда
6. `webapp/master/services.html` - управление услугами
7. `webapp/master/services.js` - логика CRUD услуг

### Обновлённые файлы:
- `bot/handlers/api.py` - +8 новых endpoints
- `bot/handlers/master.py` - упрощён (удалён FSM)
- `webapp/master/master.css` - добавлены стили для services

### Метрики:
- **Тесты:** +8 новых unit-тестов
- **Coverage:** ожидаем ~75% (было ~70%)
- **Endpoints:** +8 API routes
- **Строк кода:** ~1500 новых, ~200 удалённых

### Документация:
- Обновить `SPRINT_7_PLAN.md` (отметить прогресс)
- Создать `ADMIN_ANALYTICS.md` (документация метрик)
- Обновить `ROADMAP.md` (Sprint 7 статус)

---

## 🎯 Критерии успеха

### Admin Analytics:
- ✅ Все 4 метрики работают (retention, cohorts, funnel, growth)
- ✅ Дашборд открывается в Telegram
- ✅ Графики рендерятся корректно
- ✅ Данные обновляются в реальном времени
- ✅ Unit-тесты проходят (>80% coverage)

### Миграция услуг:
- ✅ Мастер может создавать услугу через Mini App
- ✅ Редактирование работает (модальное окно)
- ✅ Удаление с подтверждением
- ✅ Список обновляется после действий
- ✅ Старый FSM-интерфейс удалён из бота

### Техническое качество:
- ✅ Нет ошибок в логах
- ✅ API endpoints документированы
- ✅ Type hints везде
- ✅ Код прошёл pre-commit hooks (black, flake8, mypy)

---

## 🚧 Риски и митигация

### Риск 1: Сложность SQL запросов для cohort analysis
**Митигация:** Начать с простого GROUP BY, оптимизировать позже. Использовать EXPLAIN ANALYZE.

### Риск 2: Chart.js интеграция может занять больше времени
**Митигация:** Использовать готовые примеры из документации Chart.js. Не изобретать велосипед.

### Риск 3: Telegram WebApp signature validation
**Митигация:** Использовать готовую библиотеку `aiogram.utils.web_app` для валидации. Пример есть в документации.

### Риск 4: Адаптивность на мобильных устройствах
**Митигация:** Тестировать параллельно на Desktop и Mobile. CSS Grid адаптируется автоматически.

---

## 📝 Что НЕ входит в этот план (отложено)

### Sprint 7 Block 2 (4-5 дней):
- База клиентов в Mini App (поиск, фильтры)
- Финансовая аналитика в Mini App (графики доходов)

### Sprint 7 Block 3 (3-4 дня):
- Календарь записей в Mini App (FullCalendar.js)
- Drag&drop для переноса записей

### Future Sprints:
- SMS уведомления (SMS.RU интеграция)
- Дополнительные платёжные системы (кроме Telegram Stars)
- Групповые записи
- Мультиарендность (несколько мастеров в салоне)

---

## 🎉 Следующие шаги (после 3 дней)

1. **Code review** текущих изменений
2. **Деплой на production** (admin dashboard + services migration)
3. **Сбор feedback** от бета-тестеров (1-2 дня)
4. **Итерация** на основе feedback
5. **Переход к Sprint 7 Block 2** (база клиентов в Mini App)

---

## 📞 Контакты и ресурсы

- **ROADMAP:** [ROADMAP.md](ROADMAP.md)
- **Sprint 7 План:** [SPRINT_7_PLAN.md](SPRINT_7_PLAN.md)
- **Реферальная программа:** [REFERRAL_PROGRAM_IMPLEMENTATION.md](REFERRAL_PROGRAM_IMPLEMENTATION.md)
- **Chart.js Docs:** https://www.chartjs.org/docs/latest/
- **Telegram WebApp Docs:** https://core.telegram.org/bots/webapps

---

**Готов к работе! 🚀**

*План составлен: 5 декабря 2025*  
*Исполнитель: Development Team*  
*Статус: Утверждён ✅*
