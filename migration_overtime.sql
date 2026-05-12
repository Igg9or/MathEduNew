-- Миграция: дополнительное время (overtime) в дуэли + last_correct_at
-- Дата: 2026-05-11

ALTER TABLE duel_matches
    ADD COLUMN IF NOT EXISTS player1_last_correct_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS player2_last_correct_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS overtime_active BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS overtime_started_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS overtime_ended_at TIMESTAMP;

ALTER TABLE duel_match_answers
    ADD COLUMN IF NOT EXISTS is_overtime BOOLEAN DEFAULT FALSE;
