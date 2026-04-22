-- Выполните эти запросы вручную в PostgreSQL
-- Они нужны для корректной работы самостоятельной работы и функции "завершить урок"

-- 1. Добавляем флаг завершения урока
ALTER TABLE lessons ADD COLUMN IF NOT EXISTS ended BOOLEAN DEFAULT FALSE;

-- 2. Проверка: убедитесь, что в lessons уже есть колонки is_self_work, join_token, room_code
-- Если чего-то нет — добавьте:
-- ALTER TABLE lessons ADD COLUMN IF NOT EXISTS is_self_work BOOLEAN DEFAULT FALSE;
-- ALTER TABLE lessons ADD COLUMN IF NOT EXISTS join_token TEXT;
-- ALTER TABLE lessons ADD COLUMN IF NOT EXISTS room_code INTEGER;
