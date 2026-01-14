import json
from services.template_importer import import_templates_from_json
from app import get_db

JSON_FILES = [
    "templates5.json",
    "templates6.json",
    "templates7.json",
    "templates8.json",
    "templates9.json",
    "templates5_tetrad.json"
]

conn = get_db()

for file in JSON_FILES:
    print(f"📂 Загружаю {file}...")

    try:
        with open(file, encoding="utf-8") as f:
            json_text = f.read()
    except FileNotFoundError:
        print(f"❌ Файл {file} не найден")
        continue

    if not json_text.strip():
        print(f"⚠️ Файл {file} пустой")
        continue

    ok, msg = import_templates_from_json(conn, json_text)
    print("✅" if ok else "❌", msg)

conn.close()

print("🎉 Импорт завершён")
