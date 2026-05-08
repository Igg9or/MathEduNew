import app
import psycopg2
import re

client = app.app.test_client()

conn = psycopg2.connect(dbname="mathdbnew", user="mathuser", password="1501", host="localhost")
cursor = conn.cursor()

# Find the class for lesson 310
cursor.execute("SELECT class_id FROM lessons WHERE id = 310")
class_id = cursor.fetchone()[0]
print("Lesson 310 class_id:", class_id)

# Find a student in that class
cursor.execute("SELECT id FROM users WHERE role='student' AND class_id = %s LIMIT 1", (class_id,))
row = cursor.fetchone()
if not row:
    print("No student found in that class!")
    conn.close()
    exit(1)
student_id = row[0]
conn.close()

print("Student ID:", student_id)

with client.session_transaction() as sess:
    sess["user_id"] = student_id
    sess["role"] = "student"
    sess["school_id"] = 1

with app.app.app_context():
    app.g.school_id = 1
    resp = client.get("/lesson/310")
    print("Status:", resp.status_code)
    if resp.status_code == 302:
        print("Redirect location:", resp.headers.get('Location'))
    html = resp.data.decode("utf-8", errors="replace")
    m = re.search(r"window\.duelConfig = \{([^}]+)\}", html, re.DOTALL)
    if m:
        print("duelConfig found:", m.group(0))
    else:
        print("duelConfig NOT found!")
    if "duelTimer" in html:
        print("duelTimer found in HTML")
    else:
        print("duelTimer NOT found")
    if "Ожидание начала раунда" in html:
        print("Waiting state shown")
    else:
        print("Active duel content shown")
