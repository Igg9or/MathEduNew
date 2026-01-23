import sqlite3
from app import DATABASE

def migrate():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        # Миграция для lesson_tasks.template_id
        cursor.execute("PRAGMA table_info(lesson_tasks)")
        lesson_tasks_columns = [col[1] for col in cursor.fetchall()]
        if 'template_id' not in lesson_tasks_columns:
            print("Добавляем столбец template_id в lesson_tasks...")
            cursor.execute('''
                ALTER TABLE lesson_tasks
                ADD COLUMN template_id INTEGER REFERENCES task_templates(id)
            ''')
            print("✅ template_id добавлен.")

        # ✅ Миграция для users.grade
        cursor.execute("PRAGMA table_info(users)")
        users_columns = [col[1] for col in cursor.fetchall()]
        if 'grade' not in users_columns:
            print("Добавляем столбец grade в users...")
            cursor.execute('''
                ALTER TABLE users
                ADD COLUMN grade INTEGER
            ''')
            print("✅ grade добавлен.")
        
        conn.commit()
        print("🎉 Все миграции успешно выполнены!")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
