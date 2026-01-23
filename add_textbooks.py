import psycopg2

# Укажи свои данные для подключения
conn = psycopg2.connect(
    dbname="mathdbnew",
    user="postgres",
    password="1501",   # <-- поменяй на свой
    host="localhost"
)
cur = conn.cursor()

# 1. Добавить недостающие столбцы (если их еще нет)
try:
    cur.execute("ALTER TABLE textbooks ADD COLUMN description VARCHAR(255);")
except psycopg2.errors.DuplicateColumn:
    conn.rollback()  # столбец уже существует

try:
    cur.execute("ALTER TABLE textbooks ADD COLUMN grade INTEGER;")
except psycopg2.errors.DuplicateColumn:
    conn.rollback()

# 2. Добавить учебники
books = [
    ('Макарычев', 'Алгебра для 5 класса', 5),
    ('Мордкович', 'Алгебра для 7-9 классов', 7),
    ('Атанасян', 'Геометрия 7-9 классы', 7),
    ('Виленкин (6 класс)', None, 6),
    ('Макарычев', 'Алгебра', 7),
    ('Макарычев', None, 8)
]

cur.executemany(
    "INSERT INTO textbooks (title, description, grade) VALUES (%s, %s, %s);",
    books
)

conn.commit()
cur.close()
conn.close()

print('Учебники добавлены!')
