import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
)
c = conn.cursor()

for table in ['task_templates', 'textbooks', 'lesson_templates']:
    print(f"\n=== {table} columns ===")
    c.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table}' 
        ORDER BY ordinal_position
    """)
    for r in c.fetchall():
        print(f"  {r[0]}: {r[1]}")

conn.close()
