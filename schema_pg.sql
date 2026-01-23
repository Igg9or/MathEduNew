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
