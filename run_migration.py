import os, psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST', 'localhost'),
    port=os.getenv('DB_PORT', '5432')
)
conn.autocommit = True  # Важно для DROP
cursor = conn.cursor()

# Удаляем таблицы в правильном порядке (зависимости)
drops = [
    "DROP TABLE IF EXISTS duel_match_answers CASCADE",
    "DROP TABLE IF EXISTS duel_matches CASCADE",
    "DROP TABLE IF EXISTS duel_round_tasks CASCADE",
    "DROP TABLE IF EXISTS duel_rounds CASCADE",
    "DROP TABLE IF EXISTS duel_brackets CASCADE",
    "DROP TABLE IF EXISTS duel_leaderboard CASCADE",
]

for sql in drops:
    try:
        cursor.execute(sql)
        print(f'OK: {sql}')
    except Exception as e:
        print(f'ERR: {sql} -> {e}')

# Создаем заново
creates = [
    ("duel_rounds", """
        CREATE TABLE duel_rounds (
            id SERIAL PRIMARY KEY,
            lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
            round_number INTEGER NOT NULL,
            round_name TEXT NOT NULL,
            time_seconds INTEGER DEFAULT 300,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            status TEXT DEFAULT 'pending',
            UNIQUE(lesson_id, round_number)
        )
    """),
    ("duel_round_tasks", """
        CREATE TABLE duel_round_tasks (
            id SERIAL PRIMARY KEY,
            round_id INTEGER NOT NULL REFERENCES duel_rounds(id) ON DELETE CASCADE,
            task_id INTEGER NOT NULL REFERENCES lesson_tasks(id) ON DELETE CASCADE,
            position INTEGER DEFAULT 1,
            UNIQUE(round_id, task_id)
        )
    """),
    ("duel_brackets", """
        CREATE TABLE duel_brackets (
            id SERIAL PRIMARY KEY,
            lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
            bracket_number INTEGER NOT NULL,
            bracket_name TEXT NOT NULL
        )
    """),
    ("duel_matches", """
        CREATE TABLE duel_matches (
            id SERIAL PRIMARY KEY,
            lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
            round_id INTEGER NOT NULL REFERENCES duel_rounds(id) ON DELETE CASCADE,
            bracket_id INTEGER NOT NULL REFERENCES duel_brackets(id) ON DELETE CASCADE,
            match_number INTEGER NOT NULL,
            player1_id INTEGER REFERENCES users(id),
            player2_id INTEGER REFERENCES users(id),
            winner_id INTEGER REFERENCES users(id),
            loser_id INTEGER REFERENCES users(id),
            player1_score INTEGER DEFAULT 0,
            player2_score INTEGER DEFAULT 0,
            player1_first_correct_at TIMESTAMP,
            player2_first_correct_at TIMESTAMP,
            status TEXT DEFAULT 'pending',
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            UNIQUE(lesson_id, round_id, match_number)
        )
    """),
    ("duel_match_answers", """
        CREATE TABLE duel_match_answers (
            id SERIAL PRIMARY KEY,
            match_id INTEGER NOT NULL REFERENCES duel_matches(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            task_id INTEGER NOT NULL REFERENCES lesson_tasks(id),
            answer TEXT,
            is_correct BOOLEAN DEFAULT FALSE,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """),
    ("duel_leaderboard", """
        CREATE TABLE duel_leaderboard (
            id SERIAL PRIMARY KEY,
            lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            final_place INTEGER,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            total_score INTEGER DEFAULT 0,
            UNIQUE(lesson_id, user_id)
        )
    """),
]

for name, sql in creates:
    try:
        cursor.execute(sql)
        print(f'OK: {name}')
    except Exception as e:
        print(f'ERR: {name} -> {e}')

# Индексы
indexes = [
    "CREATE INDEX idx_duel_rounds_lesson ON duel_rounds(lesson_id)",
    "CREATE INDEX idx_duel_round_tasks_round ON duel_round_tasks(round_id)",
    "CREATE INDEX idx_duel_brackets_lesson ON duel_brackets(lesson_id)",
    "CREATE INDEX idx_duel_matches_lesson ON duel_matches(lesson_id)",
    "CREATE INDEX idx_duel_matches_round ON duel_matches(round_id)",
    "CREATE INDEX idx_duel_matches_bracket ON duel_matches(bracket_id)",
    "CREATE INDEX idx_duel_match_answers_match ON duel_match_answers(match_id)",
    "CREATE INDEX idx_duel_leaderboard_lesson ON duel_leaderboard(lesson_id)",
]

for sql in indexes:
    try:
        cursor.execute(sql)
        print(f'OK: {sql}')
    except Exception as e:
        print(f'ERR: {sql} -> {e}')

conn.close()
print('Done')
