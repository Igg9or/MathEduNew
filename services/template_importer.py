import json
import psycopg2.extras

def import_templates_from_json(conn, json_text):
    try:
        templates = json.loads(json_text)
    except json.JSONDecodeError as e:
        return False, f"Ошибка JSON: {e}"

    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    imported = 0
    for tpl in templates:
        # Поддержка photo_url из JSON (внешняя ссылка) или photo_path (внутренний путь)
        photo = tpl.get('photo_url') or tpl.get('photo_path') or None

        cursor.execute("""
            INSERT INTO task_templates
            (textbook_id, name, question_template, answer_template,
             parameters, answer_type, conditions, photo_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (textbook_id, name) DO UPDATE SET
                question_template = EXCLUDED.question_template,
                answer_template = EXCLUDED.answer_template,
                parameters = EXCLUDED.parameters,
                answer_type = EXCLUDED.answer_type,
                conditions = EXCLUDED.conditions,
                photo_path = EXCLUDED.photo_path
        """, (
            tpl['textbook_id'],
            tpl['name'],
            tpl.get('question_template', ''),
            tpl.get('answer_template', ''),
            json.dumps(tpl.get('parameters', {})),
            tpl.get('answer_type', 'numeric'),
            tpl.get('conditions'),
            photo
        ))
        imported += 1

    conn.commit()
    return True, f"Импортировано шаблонов: {imported}"
