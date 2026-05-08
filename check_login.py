import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST")
)
c = conn.cursor()
c.execute("SELECT username, password FROM users WHERE username='Ivanova'")
row = c.fetchone()
print('Hash:', row[1])
conn.close()
