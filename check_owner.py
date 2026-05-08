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

# Кто мы?
cursor.execute("SELECT current_user, session_user")
print("Current user:", cursor.fetchone())

# Владельцы таблиц duel_*
cursor.execute("""
    SELECT schemaname, tablename, tableowner 
    FROM pg_catalog.pg_tables 
    WHERE tablename LIKE 'duel_%'
""")
rows = cursor.fetchall()
print("Duel tables owners:")
for r in rows:
    print(r)

# Проверим права на lessons
cursor.execute("SELECT pg_catalog.pg_get_userbyid(relowner) FROM pg_catalog.pg_class WHERE relname='lessons'")
print("Lessons owner:", cursor.fetchone())

conn.close()
