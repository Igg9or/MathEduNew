import re
from unidecode import unidecode


def generate_base_username(full_name: str) -> str:
    """
    Иванов Иван Денисович → IIvanov
    """
    parts = full_name.strip().split()
    if len(parts) < 2:
        raise ValueError("ФИО должно содержать минимум имя и фамилию")

    last_name = parts[0]
    first_name = parts[1]

    first_letter = unidecode(first_name[0]).upper()
    last_name = unidecode(last_name).capitalize()

    first_letter = re.sub(r'[^A-Z]', '', first_letter)
    last_name = re.sub(r'[^A-Za-z]', '', last_name)

    return f"{first_letter}{last_name}"


def generate_unique_username(conn, full_name: str) -> str:
    base = generate_base_username(full_name)

    cur = conn.cursor()
    cur.execute("""
        SELECT username
        FROM users
        WHERE username ILIKE %s
    """, (f"{base}%",))

    existing = {row[0] for row in cur.fetchall()}
    cur.close()

    if base not in existing:
        return base

    i = 2
    while f"{base}{i}" in existing:
        i += 1

    return f"{base}{i}"
