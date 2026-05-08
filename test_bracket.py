import app
import psycopg2

client = app.app.test_client()

conn = psycopg2.connect(dbname="mathdbnew", user="mathuser", password="1501", host="localhost")
cursor = conn.cursor()
cursor.execute("SELECT id FROM users WHERE role='teacher' LIMIT 1")
teacher_id = cursor.fetchone()[0]
conn.close()

print("Teacher ID:", teacher_id)

with client.session_transaction() as sess:
    sess["user_id"] = teacher_id
    sess["role"] = "teacher"
    sess["school_id"] = 1

with app.app.app_context():
    app.g.school_id = 1
    
    # Test bracket page
    resp = client.get("/teacher/duel_bracket/310")
    print("Bracket page status:", resp.status_code)
    html = resp.data.decode("utf-8", errors="replace")
    if "duel_bracket" in html or "Турнирная сетка" in html:
        print("Bracket page HTML OK")
    else:
        print("Bracket page HTML missing expected content")
    
    # Test bracket API
    resp = client.get("/api/duel/310/bracket")
    print("Bracket API status:", resp.status_code)
    data = resp.get_json()
    print("Rounds:", len(data.get('rounds', [])))
    print("Matches:", len(data.get('matches', [])))
    if data.get('matches'):
        m = data['matches'][0]
        print("Sample match keys:", list(m.keys()))
        print("Sample match:", m.get('player1_name'), "vs", m.get('player2_name'), 
              "scores:", m.get('player1_score'), ":", m.get('player2_score'))
        print("Player1 stats:", m.get('player1_stats'))
