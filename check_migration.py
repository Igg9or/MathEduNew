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
cursor = conn.cursor()

# Вариант 1: через information_schema
tables = ['duel_rounds', 'duel_round_tasks', 'duel_brackets', 'duel_matches', 'duel_match_answers', 'duel_leaderboard']
print('--- information_schema ---')
for t in tables:
    cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema='public' AND table_name = %s)", (t,))
    exists = cursor.fetchone()[0]
    print(f'{t}: {exists}')

# Вариант 2: через pg_catalog (надежнее)
print('--- pg_catalog ---')
for t in tables:
    cursor.execute("SELECT EXISTS (SELECT FROM pg_catalog.pg_tables WHERE schemaname='public' AND tablename = %s)", (t,))
    exists = cursor.fetchone()[0]
    print(f'{t}: {exists}')

# Вариант 3: попробовать SELECT
print('--- SELECT ---')
for t in tables:
    try:
        cursor.execute(f"SELECT 1 FROM {t} LIMIT 0")
        print(f'{t}: accessible')
    except Exception as e:
        print(f'{t}: {e}')

conn.close()
