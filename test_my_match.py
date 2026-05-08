import app
import psycopg2

client = app.app.test_client()

conn = psycopg2.connect(dbname="mathdbnew", user="mathuser", password="1501", host="localhost")
cursor = conn.cursor()
# Найдём ученика, который есть в матче урока 310
cursor.execute("""
    SELECT dm.player1_id FROM duel_matches dm
    JOIN duel_rounds dr ON dr.id = dm.round_id
    WHERE dr.lesson_id = 310 LIMIT 1
""")
student_id = cursor.fetchone()[0]
conn.close()

print("Student ID:", student_id)

with client.session_transaction() as sess:
    sess["user_id"] = student_id
    sess["role"] = "student"
    sess["school_id"] = 1

with app.app.app_context():
    app.g.school_id = 1
    resp = client.get("/api/duel/310/my_match")
    print("Status:", resp.status_code)
    data = resp.get_json()
    print("Match keys:", list(data.keys()) if data else None)
    if data and 'match' in data:
        print("Match status:", data['match'].get('status'))
        print("Round:", data.get('round', {}).get('round_name'))
        print("Next match:", data.get('next_match'))
