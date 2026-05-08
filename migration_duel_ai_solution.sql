-- Миграция: добавляем ai_solution в duel_match_answers
ALTER TABLE duel_match_answers ADD COLUMN IF NOT EXISTS ai_solution TEXT;
