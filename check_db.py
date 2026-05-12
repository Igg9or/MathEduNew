import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST')
)
cur = conn.cursor()
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'duel_matches' 
    ORDER BY ordinal_position
""")
print('--- duel_matches ---')
for r in cur.fetchall():
    print(r[0])
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'duel_match_answers' 
    ORDER BY ordinal_position
""")
print('--- duel_match_answers ---')
for r in cur.fetchall():
    print(r[0])
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'duel_rounds' 
    ORDER BY ordinal_position
""")
print('--- duel_rounds ---')
for r in cur.fetchall():
    print(r[0])
conn.close()
