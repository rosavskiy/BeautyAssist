-- Скрипт для анализа производительности критичных запросов
-- Запускать: psql -h localhost -U your_user -d beautyassist -f scripts/analyze_queries.sql

-- ==========================================
-- 1. АНАЛИЗ ИНДЕКСОВ
-- ==========================================

-- Размер индексов и таблиц
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Список всех индексов
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_indexes
LEFT JOIN pg_class ON pg_indexes.indexname = pg_class.relname
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;

-- ==========================================
-- 2. EXPLAIN ANALYZE для критичных запросов
-- ==========================================

-- Запрос 1: Получение записей мастера с фильтрами (get_by_master)
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT appointments.*
FROM appointments
WHERE appointments.master_id = 1
  AND appointments.start_time >= NOW()
  AND appointments.start_time <= NOW() + INTERVAL '7 days'
  AND appointments.status IN ('scheduled', 'confirmed')
ORDER BY appointments.start_time;

-- Запрос 2: Проверка конфликтов времени (check_time_conflict)
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT appointments.id
FROM appointments
WHERE appointments.master_id = 1
  AND appointments.status IN ('scheduled', 'confirmed')
  AND (
    (appointments.start_time <= '2025-12-05 10:00:00+03' AND appointments.end_time > '2025-12-05 10:00:00+03')
    OR (appointments.start_time < '2025-12-05 11:00:00+03' AND appointments.end_time >= '2025-12-05 11:00:00+03')
    OR (appointments.start_time >= '2025-12-05 10:00:00+03' AND appointments.end_time <= '2025-12-05 11:00:00+03')
  )
LIMIT 1;

-- Запрос 3: Получение записей клиента (для "Мои записи")
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT appointments.*
FROM appointments
WHERE appointments.client_id = 1
  AND appointments.status IN ('scheduled', 'confirmed')
ORDER BY appointments.start_time DESC;

-- Запрос 4: Поиск напоминаний для отправки
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT reminders.*
FROM reminders
WHERE reminders.status = 'scheduled'
  AND reminders.scheduled_time <= NOW()
ORDER BY reminders.scheduled_time
LIMIT 100;

-- Запрос 5: Поиск клиента по telegram_id
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT clients.*
FROM clients
WHERE clients.master_id = 1
  AND clients.telegram_id = 123456789;

-- ==========================================
-- 3. СТАТИСТИКА ИСПОЛЬЗОВАНИЯ ИНДЕКСОВ
-- ==========================================

-- Неиспользуемые индексы (кандидаты на удаление)
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Самые используемые индексы
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC
LIMIT 20;

-- ==========================================
-- 4. РЕКОМЕНДАЦИИ ПО VACUUM
-- ==========================================

-- Проверка необходимости VACUUM
SELECT
    schemaname,
    tablename,
    n_live_tup,
    n_dead_tup,
    ROUND(100 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_ratio,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_dead_tup DESC;

-- ==========================================
-- 5. МЕДЛЕННЫЕ ЗАПРОСЫ (требует pg_stat_statements)
-- ==========================================

-- Раскомментируйте если расширение установлено:
-- CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

/*
SELECT
    query,
    calls,
    ROUND(total_exec_time::numeric, 2) as total_time_ms,
    ROUND(mean_exec_time::numeric, 2) as avg_time_ms,
    ROUND(max_exec_time::numeric, 2) as max_time_ms
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY total_exec_time DESC
LIMIT 20;
*/
