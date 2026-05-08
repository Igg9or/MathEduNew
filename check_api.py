import psycopg2, psycopg2.extras, os, json, math
from dotenv import load_dotenv
load_dotenv()

# Copy _json_safe
def _json_safe(value):
    import datetime
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_json_safe(v) for v in value]
    elif isinstance(value, datetime.datetime):
        return value.isoformat()
    return value

conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
)
c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

lid = 311

c.execute('''
    SELECT id, round_number, round_name, status, time_seconds
    FROM duel_rounds WHERE lesson_id = %s ORDER BY round_number
''', (lid,))
rounds = [dict(r) for r in c.fetchall()]

c.execute('''
    SELECT dm.*,
           p1.full_name AS player1_name,
           p2.full_name AS player2_name,
           w.full_name AS winner_name,
           l.full_name AS loser_name,
           db.bracket_number, db.bracket_name
    FROM duel_matches dm
    LEFT JOIN users p1 ON p1.id = dm.player1_id
    LEFT JOIN users p2 ON p2.id = dm.player2_id
    LEFT JOIN users w ON w.id = dm.winner_id
    LEFT JOIN users l ON l.id = dm.loser_id
    JOIN duel_brackets db ON db.id = dm.bracket_id
    WHERE dm.lesson_id = %s
    ORDER BY dm.round_id, dm.match_number
''', (lid,))
matches = [dict(m) for m in c.fetchall()]

match_ids = [m['id'] for m in matches]
answer_stats = {}
if match_ids:
    c.execute('''
        SELECT match_id, user_id,
               COUNT(*) FILTER (WHERE is_correct = TRUE) AS correct_count,
               COUNT(*) AS total_answers
        FROM duel_match_answers
        WHERE match_id = ANY(%s)
        GROUP BY match_id, user_id
    ''', (match_ids,))
    for row in c.fetchall():
        mid = row['match_id']
        if mid not in answer_stats:
            answer_stats[mid] = {}
        answer_stats[mid][row['user_id']] = {
            'correct_count': row['correct_count'] or 0,
            'total_answers': row['total_answers'] or 0
        }

for m in matches:
    mid = m['id']
    stats = answer_stats.get(mid, {})
    m['player1_stats'] = stats.get(m['player1_id'], {'correct_count': 0, 'total_answers': 0})
    m['player2_stats'] = stats.get(m['player2_id'], {'correct_count': 0, 'total_answers': 0})
    m['player1_score'] = m['player1_score'] or 0
    m['player2_score'] = m['player2_score'] or 0

result = _json_safe({'rounds': rounds, 'matches': matches})

# Check for any issues
print(f"Rounds: {len(result['rounds'])}")
print(f"Matches: {len(result['matches'])}")

# Simulate visible rounds logic
rounds_list = result['rounds']
activeIdx = next((i for i, r in enumerate(rounds_list) if r['status'] == 'active'), -1)
if activeIdx == -1:
    for i in range(len(rounds_list)-1, -1, -1):
        if rounds_list[i]['status'] == 'completed':
            activeIdx = i
            break
if activeIdx == -1:
    activeIdx = 0
startIdx = max(0, activeIdx - 1)
endIdx = min(len(rounds_list) - 1, activeIdx + 1)
visibleRounds = rounds_list[startIdx:endIdx+1]
print(f"\nVisible rounds (activeIdx={activeIdx}):")
for r in visibleRounds:
    print(f"  {r['round_number']} ({r['round_name']}): {r['status']}")

# Simulate roundBrackets
roundBrackets = {}
for m in result['matches']:
    rid = m['round_id']
    bnum = m.get('bracket_number') or 1
    if rid not in roundBrackets:
        roundBrackets[rid] = {}
    if bnum not in roundBrackets[rid]:
        roundBrackets[rid][bnum] = []
    roundBrackets[rid][bnum].append(m)

print(f"\nRound IDs in roundBrackets: {list(roundBrackets.keys())}")
for rid, rb in roundBrackets.items():
    print(f"  round_id {rid}: brackets {list(rb.keys())}, matches {sum(len(v) for v in rb.values())}")

# Check if any visible round has no matches
for r in visibleRounds:
    rb = roundBrackets.get(r['id'])
    if not rb:
        print(f"\nWARNING: round_id {r['id']} has NO matches in roundBrackets!")

conn.close()
