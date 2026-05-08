CREATE TABLE classes (
    id SERIAL PRIMARY KEY,
    grade INTEGER NOT NULL,
    letter TEXT NOT NULL,
    UNIQUE(grade, letter)
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    full_name TEXT,
    class_id INTEGER REFERENCES classes(id),
    grade INTEGER,
    UNIQUE(username, class_id)
);

CREATE TABLE lessons (
    id SERIAL PRIMARY KEY,
    teacher_id INTEGER REFERENCES users(id),
    class_id INTEGER REFERENCES classes(id),
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE subjects (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE lesson_tasks (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER REFERENCES lessons(id),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    template_id INTEGER REFERENCES task_templates(id)
);

CREATE TABLE student_task_variants (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER REFERENCES lessons(id),
    user_id INTEGER REFERENCES users(id),
    task_id INTEGER REFERENCES lesson_tasks(id),
    variant_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lesson_id, user_id, task_id)
);

CREATE TABLE student_answers (
    task_id INTEGER REFERENCES lesson_tasks(id),
    user_id INTEGER REFERENCES users(id),
    answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, user_id)
);

CREATE TABLE textbooks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    grade INTEGER NOT NULL,
    UNIQUE(title, grade)
);

CREATE TABLE task_templates (
    id SERIAL PRIMARY KEY,
    textbook_id INTEGER REFERENCES textbooks(id),
    name TEXT NOT NULL,
    question_template TEXT NOT NULL,
    answer_template TEXT NOT NULL,
    parameters TEXT NOT NULL,
    conditions TEXT,
    answer_type TEXT DEFAULT 'numeric',
    photo_path TEXT,
    UNIQUE(textbook_id, name)
);

CREATE TABLE lesson_templates (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    question_template TEXT NOT NULL,
    answer_template TEXT NOT NULL,
    parameters TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Duel / Tournament mode tables
ALTER TABLE lessons ADD COLUMN IF NOT EXISTS is_duel BOOLEAN DEFAULT FALSE;

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
);

CREATE TABLE duel_round_tasks (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL REFERENCES duel_rounds(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES lesson_tasks(id) ON DELETE CASCADE,
    position INTEGER DEFAULT 1,
    UNIQUE(round_id, task_id)
);

CREATE TABLE duel_brackets (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    bracket_number INTEGER NOT NULL,
    bracket_name TEXT NOT NULL
);

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
);

CREATE TABLE duel_match_answers (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES duel_matches(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    task_id INTEGER NOT NULL REFERENCES lesson_tasks(id),
    answer TEXT,
    is_correct BOOLEAN DEFAULT FALSE,
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE duel_leaderboard (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    final_place INTEGER,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    total_score INTEGER DEFAULT 0,
    UNIQUE(lesson_id, user_id)
);
