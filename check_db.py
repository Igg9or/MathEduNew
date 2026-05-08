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

print("=== duel_matches columns ===")
c.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'duel_matches' 
    ORDER BY ordinal_position
""")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]}")

print("\n=== duel_rounds columns ===")
c.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'duel_rounds' 
    ORDER BY ordinal_position
""")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]}")

conn.close()
