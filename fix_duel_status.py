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

# Активируем все матчи в активных раундах
cursor.execute('''
    UPDATE duel_matches dm
    SET status = 'active', started_at = COALESCE(dm.started_at, CURRENT_TIMESTAMP)
    FROM duel_rounds dr
    WHERE dm.round_id = dr.id AND dr.status = 'active' AND dm.status = 'pending'
''')

fixed = cursor.rowcount
conn.commit()
conn.close()

print(f'Fixed {fixed} matches')
