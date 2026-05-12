from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import  math
import sympy
import os, re, json, random, time
import datetime
from datetime import datetime as dt
from math_engine import MathEngine
from task_generator import TaskGenerator
from fractions import Fraction
from sympy.parsing.sympy_parser import parse_expr
from sympy import sympify, simplify, Eq
from sympy.core.sympify import SympifyError
from openai import OpenAI
from fpdf import FPDF
from flask import send_from_directory
from pathlib import Path
from flask import render_template
from weasyprint import HTML
import tempfile
from jinja2 import Template
import markdown
import psycopg2
import psycopg2.extras
import subprocess, sys, socket, atexit, time
from dotenv import load_dotenv
import requests
import hashlib
from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify, g
from username_generator import generate_unique_username
from services.password_generator import generate_password
import secrets





load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
from devtools.playground_routes import playground_bp
app.register_blueprint(playground_bp, url_prefix="/api/dev")
from platform_admin_routes import platform_admin_bp
app.register_blueprint(platform_admin_bp, url_prefix="/platform")



def verify_password(conn, stored_hash: str, plain_password: str) -> bool:
    print("DEBUG verify_password")
    print("stored_hash =", stored_hash[:30])
    print("plain_password =", plain_password)



@app.after_request
def add_header(response):
    """
    Добавляем заголовки, запрещающие кеширование страниц и статических файлов.
    Это помогает избежать проблем с "зависшей" авторизацией на планшетах.
    """
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

from flask import has_request_context

@app.before_request
def load_context():
    g.user_id = session.get('user_id')
    g.role = session.get('role')
    g.school_id = session.get('school_id')
    g.is_platform_admin = (g.role == 'platform_admin')



client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))




from flask import session

def get_db():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )
    conn.autocommit = False  # Важно!

    cur = conn.cursor()
    is_admin = session.get('role') == 'platform_admin'
    cur.execute("SELECT set_config('app.is_platform_admin', %s, true)", ('true' if is_admin else 'false',))
    school_id = session.get('school_id')
    cur.execute("SELECT set_config('app.school_id', %s, true)", (str(school_id) if school_id else '-1',))
    cur.close()
    return conn

def cleanup_guest_students():

    print("[CLEANUP] Cleaning old guest students...")

    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )

    cursor = conn.cursor()

    try:

        cursor.execute("""
        DELETE FROM student_answers
        WHERE user_id IN (
            SELECT id FROM users
            WHERE is_guest = TRUE
            AND created_at < NOW() - INTERVAL '3 days'
        )
        """)

        cursor.execute("""
        DELETE FROM student_task_variants
        WHERE user_id IN (
            SELECT id FROM users
            WHERE is_guest = TRUE
            AND created_at < NOW() - INTERVAL '3 days'
        )
        """)

        cursor.execute("""
        DELETE FROM student_seats
        WHERE student_id IN (
            SELECT id FROM users
            WHERE is_guest = TRUE
            AND created_at < NOW() - INTERVAL '3 days'
        )
        """)

        cursor.execute("""
        DELETE FROM users
        WHERE is_guest = TRUE
        AND created_at < NOW() - INTERVAL '3 days'
        """)

        conn.commit()

        print("[OK] Guest cleanup finished")

    finally:
        conn.close()

@app.route('/')
def home():
    if 'user_id' in session:
        if session['role'] == 'student':
            return redirect(url_for('student_dashboard'))
        else:
            return redirect(url_for('teacher_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        print("RAW FORM:", request.form)
        username = request.form['username'].strip()
        password = request.form['password']

        print("LOGIN ATTEMPT:", repr(username), repr(password))

        conn = get_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute(
            "SELECT id, username, password, role, full_name, school_id FROM users WHERE username = %s",
            (username,)
        )
        user = cursor.fetchone()

        print("USER FOUND:", bool(user))
        if user:
            print("STORED HASH:", user['password'])
            try:
                result = verify_password(conn, user['password'], password)
                print("PASSWORD CHECK RESULT:", result)
            except Exception as e:
                print("PASSWORD CHECK ERROR:", e)
                result = False

        else:
            result = False

        conn.close()

        if user and result:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            session['school_id'] = user['school_id']

            print("LOGIN SUCCESS")

            if user['role'] == 'student':
                return redirect(url_for('student_dashboard'))

            elif user['role'] == 'platform_admin':
                return redirect(url_for('platform_admin.schools_page'))

            else:
                # teacher и admin
                return redirect(url_for('teacher_dashboard'))

        print("LOGIN FAILED")
        return render_template('auth.html', error="Неверное имя пользователя или пароль")

    return render_template('auth.html')


def verify_password(conn, stored_hash: str, plain_password: str) -> bool:
    """
    Поддержка ВСЕХ форматов:
    - werkzeug: scrypt
    - werkzeug: pbkdf2
    - PostgreSQL crypt() (bcrypt, md5, etc)
    """

    if not stored_hash:
        return False

    # 1️⃣ Werkzeug (scrypt, pbkdf2 и будущие)
    if stored_hash.startswith(("scrypt:", "pbkdf2:")):
        try:
            return check_password_hash(stored_hash, plain_password)
        except Exception as e:
            print("Werkzeug hash check error:", e)
            return False

    # 2️⃣ PostgreSQL crypt (старые пароли)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT crypt(%s, %s) = %s",
            (plain_password, stored_hash, stored_hash)
        )
        ok = cur.fetchone()[0]
        cur.close()
        return bool(ok)
    except Exception as e:
        print("Postgres crypt check error:", e)
        return False



@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM subjects WHERE school_id = %s ORDER BY id", (g.school_id,))
    subjects = cursor.fetchall()
    conn.close()
    
    return render_template('student_dashboard.html', 
                         full_name=session['full_name'],
                         subjects=subjects)

@app.route('/teacher/dashboard')
def teacher_dashboard():
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))
    
    return render_template('teacher_dashboard.html', 
                         full_name=session['full_name'])


@app.route('/teacher/get_lessons')
def get_lessons():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    
    class_full = request.args.get('grade')  # Формат "6В"
    grade = class_full[:-1]  # "6"
    letter = class_full[-1]  # "В"
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Находим ID класса
        cursor.execute("""
    SELECT id
    FROM classes
    WHERE grade = %s AND letter = %s AND school_id = %s
""", (grade, letter, g.school_id))

        class_id = cursor.fetchone()
        
        if not class_id:
            return jsonify({'lessons': []})
        
        # Получаем уроки для этого класса
        cursor.execute('''
    SELECT l.id, l.title, l.date 
    FROM lessons l
    WHERE l.class_id = %s
      AND l.teacher_id = %s
      AND l.school_id = %s
    ORDER BY l.date DESC
''', (class_id[0], session['user_id'], g.school_id))

        
        lessons = cursor.fetchall()
        return jsonify({
            'lessons': [dict(lesson) for lesson in lessons]
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()



@app.route('/teacher/edit_lesson/<int:lesson_id>')
def edit_lesson(lesson_id):
    # 🔒 Проверка доступа
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # --------------------------------------------------
        # 1️⃣ Информация об уроке (добавили room_code + is_duel)
        # --------------------------------------------------
        cursor.execute('''
            SELECT 
                l.id,
                l.title,
                l.date,
                l.join_token,
                l.room_code,
                l.is_duel,
                c.grade,
                c.letter
            FROM lessons l
            JOIN classes c ON l.class_id = c.id
            WHERE l.id = %s
              AND l.teacher_id = %s
              AND l.school_id = %s
              AND c.school_id = %s
        ''', (lesson_id, session['user_id'], g.school_id, g.school_id))

        lesson = cursor.fetchone()
        if not lesson:
            return redirect(url_for('teacher_dashboard'))

        # --------------------------------------------------
        # 2️⃣ ЗАДАНИЯ УРОКА
        # --------------------------------------------------
        cursor.execute('''
            SELECT
                lt.id,
                lt.question,
                lt.answer,
                lt.template_id,
                lt.photo_path,
                tt.name AS template_name
            FROM lesson_tasks lt
            LEFT JOIN task_templates tt ON lt.template_id = tt.id
            WHERE lt.lesson_id = %s
              AND lt.school_id = %s
            ORDER BY lt.position ASC, lt.id ASC
        ''', (lesson_id, g.school_id))

        tasks = cursor.fetchall()

        # --------------------------------------------------
        # 3️⃣ Учебники
        # --------------------------------------------------
        cursor.execute('''
            SELECT *
            FROM textbooks
            WHERE school_id IS NULL OR school_id = %s
            ORDER BY id, title
        ''', (g.school_id,))

        textbooks = cursor.fetchall()

        # --------------------------------------------------
        # 4️⃣ Шаблоны уроков
        # --------------------------------------------------
        cursor.execute('''
            SELECT *
            FROM lesson_templates
            WHERE school_id = %s
            ORDER BY id
        ''', (g.school_id,))

        lesson_templates = cursor.fetchall()

        # --------------------------------------------------
        # 5️⃣ Раунды дуэли (если это дуэльный урок)
        # --------------------------------------------------
        duel_rounds = []
        class_students = []
        excluded_students = []
        if lesson.get('is_duel'):
            cursor.execute('''
                SELECT id, round_number, round_name, time_seconds, status
                FROM duel_rounds
                WHERE lesson_id = %s
                ORDER BY round_number
            ''', (lesson_id,))
            duel_rounds = [dict(r) for r in cursor.fetchall()]

            for r in duel_rounds:
                cursor.execute('''
                    SELECT drt.task_id, lt.question, lt.answer, lt.template_id, lt.photo_path
                    FROM duel_round_tasks drt
                    JOIN lesson_tasks lt ON lt.id = drt.task_id
                    WHERE drt.round_id = %s
                    ORDER BY drt.position
                ''', (r['id'],))
                r['tasks'] = [dict(t) for t in cursor.fetchall()]

            # Ученики класса для управления участием
            cursor.execute('''
                SELECT u.id, u.full_name
                FROM users u
                JOIN lessons l ON l.class_id = u.class_id
                WHERE l.id = %s AND u.role = 'student' AND u.school_id = %s
                ORDER BY u.full_name
            ''', (lesson_id, g.school_id))
            class_students = [dict(s) for s in cursor.fetchall()]

            cursor.execute('''
                SELECT user_id FROM duel_excluded_students
                WHERE lesson_id = %s
            ''', (lesson_id,))
            excluded_students = [r['user_id'] for r in cursor.fetchall()]

        # --------------------------------------------------
        # 6️⃣ Рендер страницы
        # --------------------------------------------------
        return render_template(
            'edit_lesson.html',
            lesson=dict(lesson),
            tasks=[dict(t) for t in tasks],
            textbooks=[dict(tb) for tb in textbooks],
            lesson_templates=[dict(tpl) for tpl in lesson_templates],
            duel_rounds=duel_rounds,
            class_students=class_students,
            excluded_students=excluded_students
        )

    finally:
        conn.close()


@app.route('/teacher/duel_bracket/<int:lesson_id>')
def duel_bracket(lesson_id):
    """Полноэкранная турнирная сетка дуэли."""
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('''
            SELECT id, title, is_duel FROM lessons
            WHERE id = %s AND teacher_id = %s AND school_id = %s
        ''', (lesson_id, session['user_id'], g.school_id))
        lesson = cursor.fetchone()
        if not lesson:
            return redirect(url_for('teacher_dashboard'))
        return render_template('duel_bracket.html', lesson=dict(lesson))
    finally:
        conn.close()


@app.route('/duel_bracket/<int:lesson_id>')
def public_duel_bracket(lesson_id):
    """Турнирная сетка дуэли для всех (учеников и учителей)."""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('''
            SELECT id, title, is_duel, teacher_id, class_id FROM lessons
            WHERE id = %s AND school_id = %s
        ''', (lesson_id, g.school_id))
        lesson = cursor.fetchone()
        if not lesson or not lesson['is_duel']:
            return redirect(url_for('login'))

        user_id = session['user_id']
        role = session['role']

        if role == 'teacher':
            if lesson['teacher_id'] != user_id:
                return redirect(url_for('teacher_dashboard'))
        else:
            cursor.execute('''
                SELECT 1 FROM users
                WHERE id = %s AND class_id = %s AND school_id = %s
            ''', (user_id, lesson['class_id'], g.school_id))
            if not cursor.fetchone():
                return redirect(url_for('student_lessons'))

        return render_template('duel_bracket.html', lesson=dict(lesson), current_user_id=user_id, user_role=role)
    finally:
        conn.close()


@app.route('/teacher/conduct_lesson/<int:lesson_id>')
def conduct_lesson(lesson_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Получаем информацию об уроке
        cursor.execute('''
    SELECT l.id, l.title, l.date, c.grade, c.letter 
    FROM lessons l
    JOIN classes c ON l.class_id = c.id
    WHERE l.id = %s
      AND l.teacher_id = %s
      AND l.school_id = %s
      AND c.school_id = %s
''', (lesson_id, session['user_id'], g.school_id, g.school_id))

        
        lesson = cursor.fetchone()
        if not lesson:
            return redirect(url_for('teacher_dashboard'))
        
        # Получаем список учеников класса
        cursor.execute('''
    SELECT u.id, u.full_name
    FROM users u
    JOIN lessons l ON l.class_id = u.class_id
    WHERE l.id = %s
      AND u.role = 'student'
      AND u.school_id = %s
      AND l.school_id = %s
    ORDER BY u.full_name
''', (lesson_id, g.school_id, g.school_id))

        students = cursor.fetchall()
        
        # Получаем задания урока
        cursor.execute('''
    SELECT id, question
    FROM lesson_tasks
    WHERE lesson_id = %s
      AND school_id = %s
    ORDER BY id
''', (lesson_id, g.school_id))

        tasks = cursor.fetchall()
        
        return render_template('conduct_lesson.html',
                            lesson=dict(lesson),
                            students=students,
                            tasks=tasks)
    except Exception as e:
        print(f"Error: {e}")
        return "Произошла ошибка", 500
    finally:
        conn.close()


@app.route('/teacher/create_lesson', methods=['POST'])
def create_lesson():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()

    # 🔹 НОВОЕ: режим самостоятельной + без retry + дуэль
    is_self_work = data.get('is_self_work', False)
    disable_retry = data.get('disable_retry', False)
    is_duel = data.get('is_duel', False)

    class_full = data['grade']  # Формат "6В"
    
    try:
        grade = int(class_full[:-1])  # "6"
        letter = class_full[-1]       # "В"
    except Exception:
        return jsonify({'error': 'Invalid class format'}), 400
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Находим ID класса
        cursor.execute(
    "SELECT id FROM classes WHERE grade = %s AND letter = %s AND school_id = %s",
    (grade, letter, g.school_id)
)

        class_row = cursor.fetchone()
        
        if not class_row:
            return jsonify({'error': 'Class not found'}), 404
        
        class_id = class_row['id']

        # 🔹 СОЗДАЁМ УРОК (добавили is_self_work)
        join_token = secrets.token_urlsafe(8)
        room_code = generate_room_code(conn)

        cursor.execute('''
        INSERT INTO lessons (
teacher_id,
class_id,
title,
date,
is_self_work,
disable_retry,
is_duel,
school_id,
join_token,
room_code
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
RETURNING id, join_token, room_code
        ''', (
session['user_id'],
class_id,
data['title'],
data['date'],
is_self_work,
disable_retry,
is_duel,
g.school_id,
join_token,
room_code
))

        row = cursor.fetchone()

        if not row:
            raise Exception("Ошибка создания урока — RETURNING не вернул данные")

        lesson_id = row[0]
        join_token = row[1]
        room_code = row[2]


        
        conn.commit()
        
        return jsonify({
            'success': True,
            'lesson_id': lesson_id,
            'join_url': f"/join/{join_token}",
            'room_code': room_code
        })

    except Exception as e:
        conn.rollback()
        print(f"Error creating lesson: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/teacher/update_lesson/<int:lesson_id>', methods=['POST'])
def update_lesson(lesson_id):
    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        task_ids = []
        for task in data['tasks']:
            if task.get('id'):
                cursor.execute("""
    UPDATE lesson_tasks
    SET
        question = %s,
        answer = %s,
        template_id = %s,
        position = %s,
        photo_path = %s
    WHERE id = %s
      AND school_id = %s
""", (
    task['question'],
    task['answer'],
    task.get('template_id'),
    task['position'],
    task.get('photo_path'),
    task['id'],
    g.school_id
))
                task_ids.append(task['id'])

            else:
                cursor.execute("""
    INSERT INTO lesson_tasks
    (lesson_id, question, answer, template_id, position, school_id, photo_path)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING id
""", (
    lesson_id,
    task['question'],
    task['answer'],
    task.get('template_id'),
    task['position'],
    g.school_id,
    task.get('photo_path')
))
                new_id = cursor.fetchone()[0]
                task_ids.append(new_id)


        conn.commit()
        return jsonify({'success': True, 'task_ids': task_ids})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})

    finally:
        conn.close()



@app.route('/teacher/delete_task/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    conn = get_db()
    try:
        cursor = conn.cursor()

        # Удаляем ТОЛЬКО задания уроков этого учителя
        cursor.execute("""
    DELETE FROM lesson_tasks lt
    USING lessons l
    WHERE lt.id = %s
      AND lt.lesson_id = l.id
      AND l.teacher_id = %s
      AND lt.school_id = %s
      AND l.school_id = %s
""", (task_id, session['user_id'], g.school_id, g.school_id))


        if cursor.rowcount == 0:
            conn.rollback()
            return jsonify({'success': False, 'error': 'Not found'}), 404

        conn.commit()
        return jsonify({'success': True})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/teacher/manage_students')
def manage_students():
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("""
        SELECT *
        FROM classes
        WHERE school_id = %s
        ORDER BY grade, letter
    """, (g.school_id,))

    classes = cursor.fetchall()
    conn.close()
    
    return render_template('manage_students.html', classes=classes)

@app.route('/teacher/get_students')
def get_students():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    
    class_id = request.args.get('class_id')
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('''
    SELECT u.id, u.username, u.full_name, u.grade
    FROM users u
    JOIN classes c ON c.id = u.class_id
    WHERE u.role = 'student'
      AND u.class_id = %s
      AND u.school_id = %s
      AND c.school_id = %s
    ORDER BY u.full_name
''', (class_id, g.school_id, g.school_id))

    students = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'students': [dict(student) for student in students]
    })

@app.route('/teacher/add_student', methods=['POST'])
def add_student():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}

    full_name = (data.get('full_name') or '').strip()
    class_id = data.get('class_id')
    teacher_password = (data.get('password') or '').strip()

    if not full_name or not class_id:
        return jsonify({'success': False, 'error': 'Invalid payload'}), 400

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # 🔹 логин (как раньше)
        username = generate_unique_username(conn, full_name)

        # 🔹 пароль: либо от учителя, либо авто
        if teacher_password:
            plain_password = teacher_password
            password_was_generated = False
        else:
            plain_password = generate_password()
            password_was_generated = True

        cursor.execute("""
            INSERT INTO users (username, password, role, full_name, class_id, school_id)
            VALUES (%s, %s, 'student', %s, %s, %s)
        """, (
            username,
            generate_password_hash(plain_password),
            full_name,
            class_id,
            g.school_id
        ))

        conn.commit()

        # 🔹 ответ
        response = {
            'success': True,
            'username': username
        }

        # показываем пароль ТОЛЬКО если он был сгенерирован
        if password_was_generated:
            response['password'] = plain_password

        return jsonify(response)

    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({
            'success': False,
            'error': 'Логин уже существует. Попробуйте другой.'
        }), 409

    finally:
        conn.close()





@app.route('/teacher/delete_student/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("""
    DELETE FROM users
    WHERE id = %s
      AND role = 'student'
      AND school_id = %s
""", (student_id, g.school_id))

        conn.commit()
        return jsonify({'success': cursor.rowcount > 0})
    finally:
        conn.close()


@app.route('/student/lessons')
def student_lessons():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Получаем класс ученика
        cursor.execute("""
    SELECT class_id
    FROM users
    WHERE id = %s AND school_id = %s
""", (session['user_id'], g.school_id))

        class_id = cursor.fetchone()
        
        if not class_id:
            return "У вас не указан класс", 400
        
        class_id = class_id[0]
        
        # Получаем уроки для этого класса
        cursor.execute('''
    SELECT
        l.id,
        l.title,
        l.date,
        u.full_name AS teacher_name,
        COALESCE(
            ROUND(
                (SUM(CASE
                    WHEN sa.is_correct AND NOT COALESCE(sa.retry_used, FALSE) THEN 1
                    WHEN sa.is_correct AND COALESCE(sa.retry_used, FALSE) THEN 0.5
                    ELSE 0
                END)::numeric /
                NULLIF(COUNT(lt.id), 0)) * 100
            ),
            0
        ) AS progress
    FROM lessons l
    JOIN users u ON l.teacher_id = u.id

    LEFT JOIN lesson_tasks lt
        ON lt.lesson_id = l.id AND lt.school_id = %s

    LEFT JOIN student_answers sa
        ON sa.task_id = lt.id
       AND sa.user_id = %s
       AND sa.school_id = %s

    WHERE l.class_id = %s
      AND l.school_id = %s
    GROUP BY l.id, u.full_name
    ORDER BY l.date DESC
''', (g.school_id, session['user_id'], g.school_id, class_id, g.school_id))

        lessons = cursor.fetchall()
        
        return render_template('student_lessons.html', 
                            lessons=lessons,
                            full_name=session['full_name'])
    except Exception as e:
        print(f"Error: {e}")
        return "Произошла ошибка", 500
    finally:
        conn.close()

@app.route('/join/<path:token>', methods=['GET', 'POST'])
def join_lesson(token):

    token = token.strip()
    print("JOIN TOKEN:", token)

    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )

    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # ищем урок
    cursor.execute("""
        SELECT id, class_id, school_id
        FROM lessons
        WHERE TRIM(join_token) = TRIM(%s)
    """, (token,))

    lesson = cursor.fetchone()

    if not lesson:
        conn.close()
        return "Урок не найден", 404

    # если ученик уже авторизован
    if 'user_id' in session:
        conn.close()
        return redirect(url_for('start_lesson', lesson_id=lesson['id']))

    if request.method == 'POST':

        full_name = request.form['full_name']
        seat_row = int(request.form['seat_row'])
        seat_col = int(request.form['seat_col'])

        username = generate_unique_username(conn, full_name)

        # вычисляем уровень ученика по месту
        desk_index = seat_col // 2
        seat_side = seat_col % 2

        base = 2 if desk_index % 2 == 0 else 4
        grade = base if seat_side == 0 else base + 1

        # создаём ученика (гостя)
        cursor.execute("""
            INSERT INTO users (username, role, full_name, class_id, school_id, grade, is_guest)
            VALUES (%s,'student',%s,%s,%s,%s,TRUE)
            RETURNING id
        """, (
            username,
            full_name,
            lesson['class_id'],
            lesson['school_id'],
            grade
        ))

        student_id = cursor.fetchone()['id']

        # сохраняем место (ПРИВЯЗАНО К УРОКУ)
        cursor.execute("""
            INSERT INTO student_seats
            (student_id, seat_row, seat_col, class_id, lesson_id, school_id)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            student_id,
            seat_row,
            seat_col,
            lesson['class_id'],
            lesson['id'],          # ← ВАЖНО
            lesson['school_id']
        ))

        conn.commit()

        # создаём сессию
        session['user_id'] = student_id
        session['role'] = 'student'
        session['full_name'] = full_name
        session['school_id'] = lesson['school_id']

        conn.close()

        return redirect(url_for('start_lesson', lesson_id=lesson['id']))

    conn.close()

    return render_template("join_lesson.html")

@app.route('/lesson/<int:lesson_id>')
def start_lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    student_mark = infer_student_mark(user_id)

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # 🔐 Проверка доступа ученика
        if session['role'] == 'student':
            cursor.execute('''
    SELECT 1
    FROM lessons l
    JOIN users u ON l.class_id = u.class_id
    WHERE u.id = %s
      AND u.school_id = %s
      AND l.id = %s
      AND l.school_id = %s
''', (user_id, g.school_id, lesson_id, g.school_id))

            if not cursor.fetchone():
                return redirect(url_for('student_lessons'))

        # 📘 Информация об уроке (+ is_self_work + ended + disable_retry + is_duel)
        cursor.execute('''
    SELECT 
        l.id,
        l.title,
        l.date,
        l.is_self_work,
        l.ended,
        l.disable_retry,
        l.is_duel,
        u.full_name AS teacher_name
    FROM lessons l
    JOIN users u ON l.teacher_id = u.id
    WHERE l.id = %s
      AND l.school_id = %s
''', (lesson_id, g.school_id))

        lesson = cursor.fetchone()

        if not lesson:
            return redirect(url_for('student_lessons'))

        # 📋 Задания урока (ВАЖНО: position!)
        cursor.execute('''
    SELECT id, question, answer, template_id, photo_path
    FROM lesson_tasks
    WHERE lesson_id = %s
      AND school_id = %s
    ORDER BY position ASC, id ASC
''', (lesson_id, g.school_id))

        base_tasks = cursor.fetchall()

        tasks = []

        for task in base_tasks:
            # --- проверяем сохранённый вариант ---
            cursor.execute('''
    SELECT variant_data
    FROM student_task_variants
    WHERE lesson_id = %s
      AND user_id = %s
      AND task_id = %s
      AND school_id = %s
''', (lesson_id, user_id, task['id'], g.school_id))

            variant_row = cursor.fetchone()

            if variant_row:
                raw = variant_row['variant_data']
                if isinstance(raw, str):
                    variant_data = json.loads(raw)
                else:
                    variant_data = raw or {}

                question = variant_data.get('generated_question', task['question'])
                computed_answer = variant_data.get('computed_answer', '')
                params = variant_data.get('params', {})
                initial_choice_idx = variant_data.get('initial_choice_idx')
                current_choice_idx = variant_data.get('current_choice_idx')
                photo_path = task.get('photo_path', '') or variant_data.get('photo_path', '') or ''

                if task['template_id']:
                    cursor.execute(
                        'SELECT answer_type FROM task_templates WHERE id = %s',
                        (task['template_id'],)
                    )
                    r = cursor.fetchone()
                    answer_type = r['answer_type'] if r else 'numeric'
                else:
                    answer_type = 'numeric'

            else:
                # --- генерация нового варианта ---
                if task['template_id']:
                    cursor.execute(
                        'SELECT * FROM task_templates WHERE id = %s',
                        (task['template_id'],)
                    )
                    template = cursor.fetchone()
                    template_dict = dict(template)
                    params = template_dict['parameters']
                    if isinstance(params, str):
                        params = json.loads(params)
                    template_dict['parameters'] = params

                    # Если задание с фото — генерируем вариант для правильного ответа,
                    # но question оставляем пустым (показывается только фото)
                    if template_dict.get('photo_path'):
                        variant = TaskGenerator.generate_task_variant(
                            template_dict,
                            band=student_mark
                        )
                        question = ''
                        computed_answer = variant['correct_answer']
                        params = variant['params']
                        choice_idx = variant.get('choice_idx')
                        answer_type = template_dict.get('answer_type', 'numeric')
                    else:
                        variant = TaskGenerator.generate_task_variant(
                            template_dict,
                            band=student_mark
                        )

                        question = variant['question']
                        computed_answer = variant['correct_answer']
                        params = variant['params']
                        choice_idx = variant.get('choice_idx')

                        answer_type = template_dict.get('answer_type', 'numeric')
                else:
                    # старые задания
                    params = {}
                    question = task['question']
                    computed_answer = task['answer']
                    answer_type = 'numeric'
                    choice_idx = None

                photo_path = task.get('photo_path', '') or ''

                cursor.execute('''
    INSERT INTO student_task_variants
        (lesson_id, user_id, task_id, variant_data, school_id)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (lesson_id, user_id, task_id)
    DO UPDATE SET variant_data = EXCLUDED.variant_data,
                  created_at = CURRENT_TIMESTAMP
''', (
    lesson_id,
    user_id,
    task['id'],
    json.dumps({
        'params': params,
        'generated_question': question,
        'computed_answer': computed_answer,
        'initial_choice_idx': choice_idx,
        'current_choice_idx': choice_idx,
        'is_retry': False,
        'photo_path': photo_path,

        'retry_generated_question': None,
        'retry_computed_answer': None,
        'retry_params': None,
        'retry_choice_idx': None
    }),
    g.school_id
))


            tasks.append({
                'id': task['id'],
                'question': question,
                'correct_answer': computed_answer,
                'params': params,
                'answer_type': answer_type,
                'photo_path': photo_path
            })

        conn.commit()

        # 🎓 Класс ученика
        cursor.execute('''
    SELECT c.grade
    FROM users u
    JOIN classes c ON u.class_id = c.id
    WHERE u.id = %s
      AND u.school_id = %s
      AND c.school_id = %s
''', (user_id, g.school_id, g.school_id))

        grade_row = cursor.fetchone()
        student_grade = grade_row['grade'] if grade_row else None

        # 🎮 Если это дуэльный урок — рендерим специальный шаблон
        if lesson.get('is_duel'):
            # Получаем текущий матч ученика
            cursor.execute('''
                SELECT dm.id AS match_id, dm.player1_id, dm.player2_id,
                       p1.full_name AS player1_name, p2.full_name AS player2_name,
                       dm.player1_score, dm.player2_score, dm.status,
                       dm.overtime_active,
                       dr.id AS round_id, dr.round_number, dr.round_name, dr.time_seconds
                FROM duel_rounds dr
                LEFT JOIN duel_matches dm ON dm.round_id = dr.id
                    AND (dm.player1_id = %s OR dm.player2_id = %s)
                LEFT JOIN users p1 ON p1.id = dm.player1_id
                LEFT JOIN users p2 ON p2.id = dm.player2_id
                WHERE dr.lesson_id = %s
                ORDER BY dr.round_number
            ''', (user_id, user_id, lesson_id))
            duel_rows = cursor.fetchall()
            active_match = None
            current_round = None
            # Берём последний раунд, в котором у ученика есть матч (active или completed)
            for row in reversed(duel_rows):
                if row['round_id'] and row['match_id'] and row['status'] in ('active', 'completed'):
                    active_match = {
                        'id': row['match_id'],
                        'player1_id': row['player1_id'],
                        'player2_id': row['player2_id'],
                        'player1_name': row['player1_name'],
                        'player2_name': row['player2_name'],
                        'player1_score': row['player1_score'],
                        'player2_score': row['player2_score'],
                        'status': row['status'],
                        'overtime_active': row.get('overtime_active', False)
                    }
                    current_round = {
                        'id': row['round_id'],
                        'round_number': row['round_number'],
                        'round_name': row['round_name'],
                        'time_seconds': row['time_seconds']
                    }
                    break

            opponent_name = None
            my_score = 0
            opponent_score = 0
            if active_match:
                if active_match['player1_id'] == user_id:
                    opponent_name = active_match['player2_name']
                    my_score = active_match['player1_score'] or 0
                    opponent_score = active_match['player2_score'] or 0
                else:
                    opponent_name = active_match['player1_name']
                    my_score = active_match['player2_score'] or 0
                    opponent_score = active_match['player1_score'] or 0

            # Задания, решенные верно в основное время (не нужны в overtime)
            solved_in_main_ids = []
            if active_match and active_match.get('overtime_active'):
                cursor.execute('''
                    SELECT task_id FROM duel_match_answers
                    WHERE match_id = %s AND user_id = %s AND is_correct = TRUE
                      AND (is_overtime = FALSE OR is_overtime IS NULL)
                ''', (active_match['id'], user_id))
                solved_in_main_ids = [r['task_id'] for r in cursor.fetchall()]

            # 📋 Генерируем варианты заданий текущего раунда
            duel_tasks = []
            if current_round:
                cursor.execute('''
                    SELECT lt.id, lt.question, lt.answer, lt.template_id, lt.photo_path
                    FROM duel_round_tasks drt
                    JOIN lesson_tasks lt ON lt.id = drt.task_id
                    WHERE drt.round_id = %s
                    ORDER BY drt.position
                ''', (current_round['id'],))
                base_tasks = cursor.fetchall()

                for task in base_tasks:
                    cursor.execute('''
                        SELECT variant_data FROM student_task_variants
                        WHERE lesson_id = %s AND user_id = %s AND task_id = %s AND school_id = %s
                    ''', (lesson_id, user_id, task['id'], g.school_id))
                    variant_row = cursor.fetchone()

                    if variant_row:
                        raw = variant_row['variant_data']
                        if isinstance(raw, str):
                            variant_data = json.loads(raw)
                        else:
                            variant_data = raw or {}
                        question = variant_data.get('generated_question', task['question'])
                        computed_answer = variant_data.get('computed_answer', '')
                        photo_path = task.get('photo_path', '') or variant_data.get('photo_path', '') or ''
                        print(f"[START_LESSON] task={task['id']} user={user_id} q={question[:70]} ans={computed_answer} raw_type={type(raw)}")
                        answer_type = 'numeric'
                        if task['template_id']:
                            cursor.execute('SELECT answer_type FROM task_templates WHERE id = %s', (task['template_id'],))
                            r = cursor.fetchone()
                            answer_type = r['answer_type'] if r else 'numeric'
                    else:
                        if task['template_id']:
                            cursor.execute('SELECT * FROM task_templates WHERE id = %s', (task['template_id'],))
                            template = cursor.fetchone()
                            template_dict = dict(template)
                            params = template_dict['parameters']
                            if isinstance(params, str):
                                params = json.loads(params)
                            template_dict['parameters'] = params

                            if template_dict.get('photo_path'):
                                variant = TaskGenerator.generate_task_variant(template_dict, band=student_mark)
                                question = ''
                                computed_answer = variant['correct_answer']
                                answer_type = template_dict.get('answer_type', 'numeric')
                            else:
                                variant = TaskGenerator.generate_task_variant(template_dict, band=student_mark)
                                question = variant['question']
                                computed_answer = variant['correct_answer']
                                answer_type = template_dict.get('answer_type', 'numeric')
                        else:
                            question = task['question']
                            computed_answer = task['answer']
                            answer_type = 'numeric'

                        photo_path = task.get('photo_path', '') or ''

                        cursor.execute('''
                            INSERT INTO student_task_variants (lesson_id, user_id, task_id, variant_data, school_id)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (lesson_id, user_id, task_id)
                            DO UPDATE SET variant_data = EXCLUDED.variant_data, created_at = CURRENT_TIMESTAMP
                        ''', (
                            lesson_id, user_id, task['id'],
                            json.dumps({
                                'params': variant.get('params', {}) if task['template_id'] else {},
                                'generated_question': question,
                                'computed_answer': computed_answer,
                                'photo_path': photo_path,
                                'initial_choice_idx': variant.get('choice_idx') if task['template_id'] else None,
                                'current_choice_idx': variant.get('choice_idx') if task['template_id'] else None,
                                'is_retry': False,
                                'retry_generated_question': None,
                                'retry_computed_answer': None,
                                'retry_params': None,
                                'retry_choice_idx': None
                            }),
                            g.school_id
                        ))

                    duel_tasks.append({
                        'id': task['id'],
                        'question': question,
                        'correct_answer': computed_answer,
                        'answer_type': answer_type,
                        'photo_path': photo_path,
                        'template_id': task['template_id'],
                        'params': variant.get('params', {}) if task['template_id'] and 'variant' in locals() else {}
                    })

            conn.commit()

            return render_template(
                'student_duel.html',
                lesson=dict(lesson),
                tasks=duel_tasks,
                user_id=user_id,
                student_grade=student_grade,
                match=active_match,
                current_round=current_round,
                opponent_name=opponent_name,
                my_score=my_score,
                opponent_score=opponent_score,
                solved_in_main_ids=solved_in_main_ids
            )

        return render_template(
            'student_lesson.html',
            lesson=dict(lesson),
            tasks=tasks,
            user_id=user_id,
            student_grade=student_grade,
            is_self_work=lesson['is_self_work'],
            lesson_ended=bool(lesson.get('ended')),
            disable_retry=bool(lesson.get('disable_retry'))
        )

    except Exception as e:
        conn.rollback()
        print(f"Error in start_lesson: {e}")
        return "Произошла ошибка при загрузке урока", 500
    finally:
        conn.close()



@app.route('/save_answer', methods=['POST'])
def save_answer():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    print("DEBUG /save_answer:", data)
    user_id = session['user_id']
    task_id = data['task_id']
    print("DEBUG /save_answer user_id:", session.get('user_id'))

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Приведение типов
    is_correct_val = data.get('is_correct', False)
    if isinstance(is_correct_val, str):
        is_correct_val = is_correct_val.lower() in ['true', '1', 'yes']
    elif isinstance(is_correct_val, int):
        is_correct_val = bool(is_correct_val)
    elif not isinstance(is_correct_val, bool):
        is_correct_val = False

    # Новый параметр retry_used
    retry_used = data.get('retry_used', False)
    if isinstance(retry_used, str):
        retry_used = retry_used.lower() in ['true', '1', 'yes']
    elif isinstance(retry_used, int):
        retry_used = bool(retry_used)
    elif not isinstance(retry_used, bool):
        retry_used = False

    # Проверяем, есть ли уже ответ
    cursor.execute('''
    SELECT answer, is_correct, retry_used 
    FROM student_answers 
    WHERE task_id = %s AND user_id = %s AND school_id = %s
''', (task_id, user_id, g.school_id))

    existing = cursor.fetchone()

    if existing:
        old_correct = existing['is_correct']
        old_retry = existing.get('retry_used', False)

        # ✅ Если ученик теперь решил правильно, обновляем статус
        if is_correct_val and not old_correct:
            new_retry = old_retry or retry_used
            cursor.execute('''
                UPDATE student_answers
                SET answer = %s,
                    is_correct = TRUE,
                    retry_used = %s,
                    answered_at = CURRENT_TIMESTAMP
                WHERE task_id = %s AND user_id = %s
            ''', (data['answer'], new_retry, task_id, user_id))
            conn.commit()
            _update_student_progress(conn, cursor, user_id, task_id)
            return jsonify({'success': True, 'updated_to_correct': True, 'is_partial': bool(new_retry)})

        # ✅ Если ученик уже перерешивал (retry_used=True), обновляем этот флаг
        elif retry_used and not old_retry:
            cursor.execute('''
                UPDATE student_answers
                SET retry_used = TRUE,
                    answered_at = CURRENT_TIMESTAMP
                WHERE task_id = %s AND user_id = %s
            ''', (task_id, user_id))
            conn.commit()
            _update_student_progress(conn, cursor, user_id, task_id)
            return jsonify({'success': True, 'retry_marked': True, 'is_partial': old_correct and True})

        # Иначе просто возвращаем старые данные
        is_partial = bool(existing['is_correct'] and existing['retry_used'])
        return jsonify({
            'success': True,
            'already_exists': True,
            'saved_answer': existing['answer'],
            'is_correct': existing['is_correct'],
            'retry_used': existing['retry_used'],
            'is_partial': is_partial
        })

    # 🔹 Если записи ещё нет — создаём новую
    cursor.execute('''
    INSERT INTO student_answers (task_id, user_id, answer, is_correct, retry_used, answered_at, school_id)
    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
    ON CONFLICT (task_id, user_id) DO UPDATE SET
        answer = EXCLUDED.answer,
        is_correct = EXCLUDED.is_correct,
        retry_used = EXCLUDED.retry_used,
        answered_at = CURRENT_TIMESTAMP,
        school_id = EXCLUDED.school_id
''', (task_id, user_id, data['answer'], is_correct_val, retry_used, g.school_id))

    conn.commit()
    _update_student_progress(conn, cursor, user_id, task_id)

    return jsonify({'success': True, 'already_exists': False, 'is_partial': bool(is_correct_val and retry_used)})


# 🔹 Хелпер: пересчёт прогресса ученика по уроку
def _update_student_progress(conn, cursor, user_id, task_id):
    cursor.execute('''
    INSERT INTO student_progress (user_id, lesson_id, total_tasks, solved_tasks, correct_tasks, school_id)
    VALUES (
        %s,
        (SELECT lesson_id FROM lesson_tasks WHERE id = %s AND school_id = %s),
        (SELECT COUNT(*) FROM lesson_tasks WHERE lesson_id = (SELECT lesson_id FROM lesson_tasks WHERE id = %s AND school_id = %s) AND school_id = %s),
        (SELECT COUNT(*) FROM student_answers WHERE user_id = %s AND school_id = %s AND task_id IN (
            SELECT id FROM lesson_tasks WHERE lesson_id = (SELECT lesson_id FROM lesson_tasks WHERE id = %s AND school_id = %s) AND school_id = %s
        )),
        (SELECT COUNT(*) FROM student_answers WHERE user_id = %s AND school_id = %s AND is_correct = TRUE AND NOT COALESCE(retry_used, FALSE) AND task_id IN (
            SELECT id FROM lesson_tasks WHERE lesson_id = (SELECT lesson_id FROM lesson_tasks WHERE id = %s AND school_id = %s) AND school_id = %s
        )),
        %s
    )
    ON CONFLICT (user_id, lesson_id) DO UPDATE SET
        solved_tasks = EXCLUDED.solved_tasks,
        correct_tasks = EXCLUDED.correct_tasks,
        last_updated = CURRENT_TIMESTAMP,
        school_id = EXCLUDED.school_id
''', (
    user_id, task_id, g.school_id,
    task_id, g.school_id, g.school_id,
    user_id, g.school_id, task_id, g.school_id, g.school_id,
    user_id, g.school_id, task_id, g.school_id, g.school_id,
    g.school_id
))
    conn.commit()


@app.route('/teacher/get_lesson_results/<int:lesson_id>')
def get_lesson_results(lesson_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Получаем список учеников и их ответов
        cursor.execute('''
    SELECT 
        u.id as user_id, 
        u.full_name,
        t.id as task_id,
        sa.answer,
        sa.is_correct,
        COALESCE(sa.retry_used, FALSE) as retry_used
    FROM lessons l
    JOIN users u ON u.class_id = l.class_id AND u.role='student'
    JOIN lesson_tasks t ON t.lesson_id = l.id AND t.school_id = %s
    LEFT JOIN student_answers sa ON sa.task_id = t.id AND sa.user_id = u.id AND sa.school_id = %s
    WHERE l.id = %s
      AND l.teacher_id = %s
      AND l.school_id = %s
      AND u.school_id = %s
    ORDER BY u.full_name, t.id
''', (g.school_id, g.school_id, lesson_id, session['user_id'], g.school_id, g.school_id))

        
        # Формируем структуру результатов
        results = {}
        for row in cursor.fetchall():
            user_id = row['user_id']
            if user_id not in results:
                results[user_id] = {
                    'user_id': user_id,
                    'full_name': row['full_name'],
                    'tasks': []
                }
            
            is_correct = row['is_correct'] if row['is_correct'] is not None else False
            retry_used = row['retry_used'] if row['retry_used'] is not None else False
            results[user_id]['tasks'].append({
                'task_id': row['task_id'],
                'answered': row['answer'] is not None,
                'is_correct': is_correct,
                'is_partial': bool(is_correct and retry_used),
                'answer': row['answer']
            })
        
        return jsonify({
            'results': list(results.values())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/get_student_answers/<int:lesson_id>/<int:user_id>')
def get_student_answers(lesson_id, user_id):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cursor.execute('''
    SELECT task_id, answer, is_correct, COALESCE(retry_used, FALSE) AS retry_used
    FROM student_answers
    WHERE user_id = %s
      AND school_id = %s
      AND task_id IN (
        SELECT id FROM lesson_tasks WHERE lesson_id = %s AND school_id = %s
      )
''', (user_id, g.school_id, lesson_id, g.school_id))

    
    answers = cursor.fetchall()
    conn.close()
    result = []
    for answer in answers:
        d = dict(answer)
        d['is_partial'] = bool(d.get('is_correct') and d.get('retry_used'))
        result.append(d)
    print("DEBUG get_student_answers:", result)
    return jsonify(result)




@app.route('/teacher/end_lesson/<int:lesson_id>', methods=['POST'])
def end_lesson(lesson_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE lessons SET ended = TRUE WHERE id = %s AND teacher_id = %s AND school_id = %s",
            (lesson_id, session['user_id'], g.school_id)
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/lesson_status/<int:lesson_id>')
def lesson_status(lesson_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(
            "SELECT ended, is_self_work, disable_retry FROM lessons WHERE id = %s AND school_id = %s",
            (lesson_id, g.school_id)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        return jsonify({
            'ended': bool(row['ended']),
            'is_self_work': bool(row['is_self_work']),
            'disable_retry': bool(row['disable_retry'])
        })
    finally:
        conn.close()


@app.route('/teacher/get_student_progress/<int:lesson_id>')
def get_student_progress(lesson_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Получаем прогресс всех учеников
        cursor.execute('''
            SELECT 
                u.id as student_id,
                u.full_name,
                t.id as task_id,
                sa.answer,
                sa.is_correct,
                COALESCE(sa.retry_used, FALSE) as retry_used
            FROM users u
            JOIN lessons l ON u.class_id = l.class_id
            JOIN lesson_tasks t ON t.lesson_id = l.id
            LEFT JOIN student_answers sa ON sa.task_id = t.id AND sa.user_id = u.id
            WHERE l.id = %s AND u.role = 'student'
            ORDER BY u.full_name, t.id
        ''', (lesson_id,))
        
        # Формируем структуру результатов
        students = {}
        for row in cursor.fetchall():
            student_id = row['student_id']
            if student_id not in students:
                students[student_id] = {
                    'student_id': student_id,
                    'full_name': row['full_name'],
                    'tasks': []
                }
            
            is_correct = row['is_correct'] if row['is_correct'] is not None else False
            retry_used = row['retry_used'] if row['retry_used'] is not None else False
            students[student_id]['tasks'].append({
                'task_id': row['task_id'],
                'answered': row['answer'] is not None,
                'is_correct': is_correct,
                'is_partial': bool(is_correct and retry_used)
            })
        
        # Рассчитываем прогресс для каждого студента
        result = []
        for student in students.values():
            score_sum = sum(1 if task['is_correct'] and not task['is_partial'] else (0.5 if task['is_partial'] else 0) for task in student['tasks'])
            total_tasks = len(student['tasks'])
            progress = round((score_sum / total_tasks) * 100) if total_tasks > 0 else 0
            
            result.append({
                'student_id': student['student_id'],
                'full_name': student['full_name'],
                'progress': progress,
                'tasks': student['tasks']
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/teacher/manage_tasks')
def manage_tasks():
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))
    
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("""
    SELECT *
    FROM textbooks
    WHERE school_id IS NULL OR school_id = %s
    ORDER BY grade, title
""", (g.school_id,))


        textbooks = cursor.fetchall()
        cursor.close()
        return render_template('manage_tasks.html', 
                            full_name=session['full_name'],
                            textbooks=textbooks)
    except Exception as e:
        print(f"Error fetching textbooks: {e}")
        return "Произошла ошибка при загрузке учебников", 500
    finally:
        conn.close()

@app.route('/teacher/manage_tasks/<int:textbook_id>')
def textbook_tasks(textbook_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))
    
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 1️⃣ Получаем учебник (ГЛОБАЛЬНЫЙ)
        cursor.execute("""
            SELECT *
            FROM textbooks
            WHERE id = %s
              AND school_id IS NULL
        """, (textbook_id,))

        textbook = cursor.fetchone()
        if not textbook:
            flash('Учебник не найден', 'error')
            return redirect(url_for('manage_tasks'))

        # 2️⃣ Получаем шаблоны заданий (ТОЛЬКО ГЛОБАЛЬНЫЕ)
        cursor.execute("""
            SELECT *,
                   ROW_NUMBER() OVER (ORDER BY id) AS task_number
            FROM task_templates
            WHERE textbook_id = %s
              AND school_id IS NULL
            ORDER BY id
        """, (textbook_id,))

        templates = cursor.fetchall()

        return render_template(
            'textbook_tasks.html',
            full_name=session['full_name'],
            textbook=dict(textbook),
            templates=templates
        )

    except Exception as e:
        print(f"Error loading textbook tasks: {e}")
        flash('Произошла ошибка при загрузке заданий', 'error')
        return redirect(url_for('manage_tasks'))
    finally:
        conn.close()

@app.route('/api/textbooks/<int:textbook_id>/templates')
def api_textbook_templates(textbook_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute("""
            SELECT id, name,
                   question_template, answer_template, parameters
            FROM task_templates
            WHERE textbook_id = %s
              AND school_id IS NULL
            ORDER BY id
        """, (textbook_id,))

        templates = [dict(t) for t in cursor.fetchall()]

        return jsonify({
            'success': True,
            'templates': templates
        })
    finally:
        conn.close()


@app.route('/teacher/add_task_template', methods=['POST'])
def add_task_template():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('''
    INSERT INTO task_templates 
    (textbook_id, name, question_template, answer_template, parameters, school_id)
    VALUES (%s, %s, %s, %s, %s, NULL)
    RETURNING id
''', (
    data['textbook_id'],
    data['name'],
    data['question_template'],
    data['answer_template'],
    json.dumps(data['parameters'])
))
        template_id = cursor.fetchone()[0]

        
        conn.commit()
        return jsonify({
            'success': True,
            'template_id': cursor.lastrowid
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/teacher/update_task_template/<int:template_id>', methods=['POST'])
def update_task_template(template_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("""
    UPDATE task_templates SET
        name = %s,
        question_template = %s,
        answer_template = %s,
        parameters = %s
    WHERE id = %s
""", (
    data['name'],
    data['question_template'],
    data['answer_template'],
    json.dumps(data['parameters']),
    template_id
))

        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/teacher/delete_task_template/<int:template_id>', methods=['DELETE'])
def delete_task_template(template_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(
    'DELETE FROM task_templates WHERE id = %s',
    (template_id,)
)


        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()
        

@app.route('/teacher/add_textbook', methods=['POST'])
def add_textbook():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    title = data.get('title')
    description = data.get('description')
    grade = data.get('grade')
    
    if not title or not grade:
        return jsonify({'success': False, 'error': 'Название и класс обязательны'})
    
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('''
            INSERT INTO textbooks (title, description, grade, school_id)
VALUES (%s, %s, %s, NULL)

            RETURNING id
        ''', (title, description, grade, g.school_id))
        textbook_id = cursor.fetchone()[0]

        
        conn.commit()
        return jsonify({
            'success': True,
            'textbook_id': textbook_id
        })
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Учебник с таким названием и классом уже существует'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

# Маршрут для сохранения шаблона
@app.route('/api/templates', methods=['POST'])
def save_template():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    required_fields = ['textbook_id', 'name', 'question', 'answer', 'parameters']
    
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Проверяем, существует ли учебник
        cursor.execute(
            'SELECT 1 FROM textbooks WHERE id = %s',
            (data['textbook_id'],)
        )
        textbook = cursor.fetchone()
        if not textbook:
            cursor.close()
            return jsonify({'error': 'Textbook not found'}), 404

        # Сохраняем шаблон (используем RETURNING для получения id)
        cursor.execute('''
    INSERT INTO task_templates
    (textbook_id, name, question_template, answer_template, parameters, school_id)
    VALUES (%s, %s, %s, %s, %s, NULL)
    RETURNING id
''', (
    data['textbook_id'],
    data['name'],
    data['question'],
    data['answer'],
    json.dumps(data['parameters'])
))


        template_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        return jsonify({
            'success': True,
            'template_id': template_id
        })
    except psycopg2.IntegrityError as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'error': 'Template with this name already exists'
        }), 400
    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        conn.close()


CYR = ' абвгдеёжзийклмнопрстуфхцчшщъыьэюя'  # пробел в начале для safety
CYR_INDEX = {ch: i for i, ch in enumerate(CYR)}


def natural_key(s: str):
    s = (s or '').lower().strip()
    parts = re.findall(r'\d+|[a-zа-яё]+', s)  # числа ИЛИ буквы; . и пробелы игнорим
    key = []
    for p in parts:
        if p.isdigit():
            key.append((0, int(p)))  # числа как int
        else:
            key.append((1, tuple(CYR_INDEX.get(ch, 999) for ch in p)))  # буквы по алфавиту
    return tuple(key)




def get_textbook_templates(textbook_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('''
            SELECT * FROM task_templates WHERE textbook_id = %s
        ''', (textbook_id,))
        templates = cursor.fetchall()
        cursor.close()
        return jsonify({
            'success': True,
            'templates': [dict(t) for t in templates]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Маршрут для удаления шаблона
@app.route('/api/templates/<int:template_id>', methods=['DELETE'])
def delete_templates(template_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM task_templates WHERE id = %s ', (template_id, g.school_id))
        deleted = cur.rowcount
        conn.commit()
        cur.close()

        
        if result.rowcount == 0:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
            
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        conn.close()

@app.route('/api/templates/<int:template_id>')
def get_template(template_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute("""
            SELECT id, textbook_id, name,
                   question_template, answer_template, parameters,
                   photo_path, answer_type, conditions
            FROM task_templates
            WHERE id = %s
        """, (template_id,))

        template = cursor.fetchone()
        cursor.close()

        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404

        return jsonify({
            'success': True,
            'template': dict(template)
        })
    finally:
        conn.close()



def compare_expressions(ans1, ans2):
    # Добавим * между числом и скобкой, если нужно
    import re
    def fix_mul(expr):
        # Заменяет 2(x+1) на 2*(x+1)
        return re.sub(r'(\d)(\()', r'\1*\2', expr)
    ans1 = fix_mul(ans1.replace("^", "**").replace(" ", ""))
    ans2 = fix_mul(ans2.replace("^", "**").replace(" ", ""))
    def can_parse_as_expr(s):
        # хотя бы одна буква и хотя бы один арифметический оператор
        return any(c.isalpha() for c in s) and any(op in s for op in "+-*/^")
    if can_parse_as_expr(ans1) and can_parse_as_expr(ans2):
        try:
            expr1 = parse_expr(ans1, evaluate=True)
            expr2 = parse_expr(ans2, evaluate=True)
            # Если разность упростилась до 0 — выражения эквивалентны
            return sympy.simplify(expr1 - expr2) == 0
        except Exception as e:
            # Если не удалось распарсить — fallback
            return ans1 == ans2
    else:
        return ans1 == ans2
    
@app.route('/api/generate_task', methods=['POST'])
def generate_task():
    data = request.get_json()
    template_id = data.get('template_id')
    
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
    'SELECT * FROM task_templates WHERE id = %s',
    (template_id,)
)
    template = cur.fetchone()

    if not template:
        return jsonify({"error": "Template not found"}), 404

    params = json.loads(template['parameters'])
    generated_params = MathEngine.generate_parameters(params)
    
    question = template['question_template'].format(**generated_params)
    answer = MathEngine.evaluate_expression(template['answer_template'], generated_params)
    
    return jsonify({
        "question": question,
        "answer": answer,
        "params": generated_params
    })

def insert_mul_sign(expr):
    expr = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr)
    expr = re.sub(r'(\))([a-zA-Z])', r'\1*\2', expr)
    return expr


def _is_fraction(s):
    return '/' in s and len(s.split('/')) == 2


def _to_float(val):
    try:
        return float(val.replace(",", "."))
    except Exception:
        try:
            if _is_fraction(val):
                num, denom = val.split('/')
                return float(num) / float(denom)
        except Exception:
            return None
    return None


def _parse_math_answer(ans):
    s = ans.replace(",", ".").replace("%", "").strip()
    if "_" in s:
        parts = s.split("_")
        if len(parts) == 2 and "/" in parts[1]:
            whole = float(parts[0])
            num, denom = parts[1].split("/")
            return whole + float(num) / float(denom)
    if " " in s and "/" in s:
        parts = s.split(" ")
        if len(parts) == 2 and "/" in parts[1]:
            whole = float(parts[0])
            num, denom = parts[1].split("/")
            return whole + float(num) / float(denom)
    if "/" in s:
        try:
            num, denom = s.split("/")
            return float(num) / float(denom)
        except Exception:
            pass
    if s.startswith("sqrt(") and s.endswith(")"):
        try:
            return math.sqrt(float(s[5:-1]))
        except:
            pass
    if "^" in s:
        try:
            base, exp = s.split("^")
            return float(base) ** float(exp)
        except:
            pass
    try:
        return float(s)
    except Exception:
        return None


def _parse_answer_list(ans):
    sep = ";" if ";" in ans else ("," if "," in ans else None)
    if sep:
        parts = [p.strip() for p in ans.split(sep)]
    else:
        parts = [ans.strip()]
    return [_parse_math_answer(p) for p in parts if p]


def _check_equivalent_answers(user, correct, answer_type="string"):
    user = str(user).replace(" ", "").replace('^', '**')
    correct = str(correct).replace(" ", "").replace('^', '**')
    if answer_type in ("numeric", "дробный"):
        try:
            if '/' in user or '/' in correct:
                return Fraction(user) == Fraction(correct)
            return abs(float(user) - float(correct)) < 1e-6
        except Exception:
            pass
    if (";" in user or "," in user) and (";" in correct or "," in correct):
        user_parts = re.split(r"[;,]", user)
        correct_parts = re.split(r"[;,]", correct)
        if len(user_parts) == len(correct_parts):
            try:
                return all(_check_equivalent_answers(u, c, answer_type) for u, c in zip(user_parts, correct_parts))
            except Exception:
                return False
    try:
        user_expr = simplify(sympify(user))
        correct_expr = simplify(sympify(correct))
        return simplify(user_expr - correct_expr) == 0
    except Exception:
        return user.lower() == correct.lower()


def _check_answer_core(user_answer, correct_answer, answer_type='numeric'):
    """
    Ядро проверки ответа. Возвращает True, False или None при ошибке парсинга.
    """
    user_answer = str(user_answer).strip()
    correct_answer = str(correct_answer).strip()

    # --- Интервалы ---
    if answer_type == "interval" or (
        ";" in correct_answer and all(
            "/" in part or "." in part or part.isdigit() or part.lstrip("-").replace(".", "").isdigit()
            for part in correct_answer.split(";"))
    ):
        interval_bounds = _parse_answer_list(correct_answer)
        if len(interval_bounds) == 2 and None not in interval_bounds:
            left, right = sorted(interval_bounds)
            user_val = _parse_math_answer(user_answer)
            if user_val is not None:
                return left < user_val < right
            return False

    # --- Строковые ---
    if answer_type == 'string':
        ua = user_answer.replace(" ", "")
        ca = correct_answer.replace(" ", "")
        if len(ua) == 1 and len(ca) == 1:
            return ua == ca
        def can_parse_as_expr(s):
            return any(c.isalpha() for c in s) and any(op in s for op in "+-*/^")
        if can_parse_as_expr(ua) and can_parse_as_expr(ca):
            try:
                ua_mod = insert_mul_sign(ua)
                ca_mod = insert_mul_sign(ca)
                expr1 = parse_expr(ua_mod.replace("^", "**"))
                expr2 = parse_expr(ca_mod.replace("^", "**"))
                return simplify(expr1 - expr2) == 0
            except Exception:
                return ua.lower() == ca.lower()
        else:
            return ua.lower() == ca.lower()

    # --- Алгебраические ---
    if answer_type == 'algebraic':
        try:
            ua_mod = insert_mul_sign(user_answer)
            ca_mod = insert_mul_sign(correct_answer)
            expr1 = simplify(sympify(ua_mod.replace("^", "**")))
            expr2 = simplify(sympify(ca_mod.replace("^", "**")))
            return simplify(expr1 - expr2) == 0
        except Exception:
            def normalize_string_answer(answer):
                return re.sub(r'\s+', '', answer).replace('\u200b', '').replace('\xa0', '').strip().lower()
            return normalize_string_answer(user_answer) == normalize_string_answer(correct_answer)

    # --- Основная проверка: списки дробей и чисел ---
    user_vals = _parse_answer_list(user_answer)
    correct_vals = _parse_answer_list(correct_answer)
    if len(user_vals) != len(correct_vals) or any(v is None for v in user_vals):
        return False
    if any(v is None for v in correct_vals):
        return None

    return all(round(u, 4) == round(c, 4) for u, c in zip(user_vals, correct_vals))


@app.route('/api/recheck_lesson/<int:lesson_id>', methods=['POST'])
def recheck_lesson(lesson_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Проверяем, что урок существует
        cursor.execute(
            "SELECT * FROM lessons WHERE id = %s AND school_id = %s",
            (lesson_id, g.school_id)
        )
        lesson = cursor.fetchone()
        if not lesson:
            return jsonify({'error': 'Lesson not found'}), 404

        # Получаем все ответы учеников для этого урока
        cursor.execute('''
            SELECT sa.task_id, sa.user_id, sa.answer, sa.is_correct,
                   stv.variant_data, tt.answer_type, lt.question as question_text
            FROM student_answers sa
            JOIN lesson_tasks lt ON sa.task_id = lt.id
            LEFT JOIN student_task_variants stv 
                   ON stv.lesson_id = lt.lesson_id 
                  AND stv.user_id = sa.user_id 
                  AND stv.task_id = sa.task_id
            LEFT JOIN task_templates tt ON lt.template_id = tt.id
            WHERE lt.lesson_id = %s AND sa.school_id = %s
        ''', (lesson_id, g.school_id))

        answers = cursor.fetchall()
        updated_count = 0
        checked_count = 0

        def _is_link_only_question(question):
            if not question:
                return False
            q = question.strip()
            return (q.startswith('http') or 
                    q.startswith('<a href=') or 
                    (len(q) < 300 and 'http' in q and '<a' in q))

        for row in answers:
            user_answer = row['answer']
            answer_type = row['answer_type'] or 'numeric'
            old_is_correct = row['is_correct']

            # Берём правильный ответ из варианта ученика (а не из base lesson_tasks)
            variant_data = row['variant_data']
            if isinstance(variant_data, str):
                import json as _json
                variant_data = _json.loads(variant_data)
            elif variant_data is None:
                variant_data = {}

            correct_answer = variant_data.get('computed_answer', '') or row.get('correct_answer', '')
            if not correct_answer:
                continue

            # Быстрая строковая проверка
            if user_answer.strip().replace(" ", "").lower() == correct_answer.strip().replace(" ", "").lower():
                new_is_correct = True
            else:
                new_is_correct = _check_answer_core(user_answer, correct_answer, answer_type)
                if new_is_correct is None:
                    continue
                checked_count += 1

            if new_is_correct != old_is_correct:
                cursor.execute('''
                    UPDATE student_answers
                    SET is_correct = %s, answered_at = CURRENT_TIMESTAMP
                    WHERE task_id = %s AND user_id = %s
                ''', (new_is_correct, row['task_id'], row['user_id']))
                updated_count += 1

        conn.commit()

        # Пересчитываем прогресс для всех учеников
        cursor.execute('''
            SELECT DISTINCT sa.user_id
            FROM student_answers sa
            JOIN lesson_tasks lt ON sa.task_id = lt.id
            WHERE lt.lesson_id = %s
        ''', (lesson_id,))
        users = cursor.fetchall()

        cursor.execute('SELECT id FROM lesson_tasks WHERE lesson_id = %s', (lesson_id,))
        tasks = [r['id'] for r in cursor.fetchall()]

        for user_row in users:
            for task_id in tasks:
                _update_student_progress(conn, cursor, user_row['user_id'], task_id)

        return jsonify({
            'success': True,
            'total_checked': len(answers),
            'server_checked': checked_count,
            'updated': updated_count
        })

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/check_answer', methods=['POST'])
def api_check_answer():
    try:
        data = request.get_json()
        print("DEBUG DATA:", data)
        
        user_answer = data['answer'].strip()
        correct_answer = data['correct_answer']
        answer_type = data.get('answer_type', 'numeric')

        def is_fraction(s):
            return '/' in s and len(s.split('/')) == 2

        def to_float(val):
            try:
                return float(val.replace(",", "."))
            except Exception:
                try:
                    if is_fraction(val):
                        num, denom = val.split('/')
                        return float(num) / float(denom)
                except Exception:
                    return None
            return None

        def float_to_fraction(val, max_denominator=1000):
            frac = Fraction(val).limit_denominator(max_denominator)
            return f"{frac.numerator}/{frac.denominator}"

        def parse_math_answer(ans):
            s = ans.replace(",", ".").replace("%", "").strip()
            if "_" in s:
                parts = s.split("_")
                if len(parts) == 2 and "/" in parts[1]:
                    whole = float(parts[0])
                    num, denom = parts[1].split("/")
                    return whole + float(num) / float(denom)
            if " " in s and "/" in s:
                parts = s.split(" ")
                if len(parts) == 2 and "/" in parts[1]:
                    whole = float(parts[0])
                    num, denom = parts[1].split("/")
                    return whole + float(num) / float(denom)
            if "/" in s:
                try:
                    num, denom = s.split("/")
                    return float(num) / float(denom)
                except Exception:
                    pass
            if s.startswith("sqrt(") and s.endswith(")"):
                try:
                    return math.sqrt(float(s[5:-1]))
                except:
                    pass
            if "^" in s:
                try:
                    base, exp = s.split("^")
                    return float(base) ** float(exp)
                except:
                    pass
            try:
                return float(s)
            except Exception:
                return None

        def parse_answer_list(ans):
            sep = ";" if ";" in ans else ("," if "," in ans else None)
            if sep:
                parts = [p.strip() for p in ans.split(sep)]
            else:
                parts = [ans.strip()]
            return [parse_math_answer(p) for p in parts if p]

        # --- Универсальный "умный" компаратор ---
        def check_equivalent_answers(user, correct, answer_type="string"):
            user = str(user).replace(" ", "").replace('^', '**')
            correct = str(correct).replace(" ", "").replace('^', '**')
            # Для дробей и чисел
            if answer_type in ("numeric", "дробный"):
                try:
                    # Fraction (1/2 == 2/4 == 0.5)
                    if '/' in user or '/' in correct:
                        return Fraction(user) == Fraction(correct)
                    return abs(float(user) - float(correct)) < 1e-6
                except Exception:
                    pass
            # Для списков из дробей/чисел
            if (";" in user or "," in user) and (";" in correct or "," in correct):
                user_parts = re.split(r"[;,]", user)
                correct_parts = re.split(r"[;,]", correct)
                if len(user_parts) == len(correct_parts):
                    try:
                        return all(check_equivalent_answers(u, c, answer_type) for u, c in zip(user_parts, correct_parts))
                    except Exception:
                        return False
            # Для выражений (алгебра/дроби)
            try:    
                user_expr = simplify(sympify(user))
                correct_expr = simplify(sympify(correct))
                return simplify(user_expr - correct_expr) == 0
            except Exception:
                # Фоллбэк: сравнение как строки (для простых кейсов)
                return user.lower() == correct.lower()

        # --- Интервалы и интервальные сравнения ---
        if answer_type == "interval" or (
            ";" in correct_answer and all(
                "/" in part or "." in part or part.isdigit() or part.lstrip("-").replace(".", "").isdigit()
                for part in correct_answer.split(";"))
        ):
            interval_bounds = parse_answer_list(correct_answer)
            if len(interval_bounds) == 2 and None not in interval_bounds:
                left, right = sorted(interval_bounds)
                user_val = parse_math_answer(user_answer)
                if user_val is not None and left < user_val < right:
                    return jsonify({
                        "is_correct": True,
                        "evaluated_answer": user_answer,
                        "correct_answer": correct_answer
                    })
                else:
                    return jsonify({
                        "is_correct": False,
                        "evaluated_answer": user_answer,
                        "correct_answer": correct_answer
                    })

        # --- Строковые задачи (старый механизм сохранён) ---
        if answer_type == 'string':
            ua = user_answer.strip().replace(" ", "")
            ca = correct_answer.strip().replace(" ", "")
            print(f"Debug: Comparing user answer '{ua}' with correct '{ca}'")
            # Оставляем проверку одного символа (например, знак сравнения)
            if len(ua) == 1 and len(ca) == 1:
                is_correct = ua == ca
            else:
                # Проверка как выражения
                def can_parse_as_expr(s):
                    return any(c.isalpha() for c in s) and any(op in s for op in "+-*/^")
                if can_parse_as_expr(ua) and can_parse_as_expr(ca):
                    try:
                        ua_mod = insert_mul_sign(ua)
                        ca_mod = insert_mul_sign(ca)
                        expr1 = parse_expr(ua_mod.replace("^", "**"))
                        expr2 = parse_expr(ca_mod.replace("^", "**"))
                        is_correct = simplify(expr1 - expr2) == 0
                    except Exception as e:
                        is_correct = ua.lower() == ca.lower()
                else:
                    is_correct = ua.lower() == ca.lower()
            return jsonify({"is_correct": is_correct, "correct_answer": correct_answer})

        # --- Алгебраические задачи ---
        if answer_type == 'algebraic':
            try:
                ua_mod = insert_mul_sign(user_answer)
                ca_mod = insert_mul_sign(correct_answer)
                expr1 = simplify(sympify(ua_mod.replace("^", "**")))
                expr2 = simplify(sympify(ca_mod.replace("^", "**")))
                is_correct = simplify(expr1 - expr2) == 0
            except Exception:
                def normalize_string_answer(answer: str) -> str:
                    import re
                    return re.sub(r'\s+', '', answer).replace('\u200b', '').replace('\xa0', '').strip().lower()

                if answer_type == "string":
                    is_correct = normalize_string_answer(user_answer) == normalize_string_answer(correct_answer)
                else:
                    is_correct = user_answer == correct_answer
            return jsonify({
                "is_correct": is_correct,
                "correct_answer": correct_answer
            })
        


        # --- Основная универсальная проверка: списки дробей и чисел ---
        user_vals = parse_answer_list(user_answer)
        correct_vals = parse_answer_list(correct_answer)
        if len(user_vals) != len(correct_vals) or any(v is None for v in user_vals):
            return jsonify({
                "is_correct": False,
                "evaluated_answer": user_answer,
                "correct_answer": correct_answer
            })
        if any(v is None for v in correct_vals):
            return jsonify({"is_correct": False, "error": "Ошибка генерации правильного ответа"})

        is_correct = all(round(u, 4) == round(c, 4) for u, c in zip(user_vals, correct_vals))
        return jsonify({
            "is_correct": is_correct,
            "evaluated_answer": user_answer,
            "correct_answer": correct_answer
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500



# В app.py добавить новый маршрут
@app.route('/api/generate_from_template/<int:template_id>')
def generate_from_template(template_id):
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT * FROM task_templates WHERE id = %s', [template_id])
        template = cursor.fetchone()
        cursor.close()

        if not template:
            return jsonify({"error": "Template not found"}), 404

        template_dict = dict(template)
        # В parameters лежит строка в JSON, нужно распарсить
        if isinstance(template_dict['parameters'], str):
            template_dict['parameters'] = json.loads(template_dict['parameters'])
        else:
            template_dict['parameters'] = template_dict['parameters']  # может быть уже dict (jsonb)
        
        # Если шаблон содержит фото (photo_path) — генерируем вариант для ответа,
        # но question оставляем пустым (показывается только фото)
        if template_dict.get('photo_path'):
            variant = TaskGenerator.generate_task_variant(template_dict)
            return jsonify({
                'question': '',
                'correct_answer': variant['correct_answer'],
                'photo_path': template_dict.get('photo_path', ''),
                'answer_type': template_dict.get('answer_type', 'numeric')
            })
        
        # Генерируем вариант
        variant = TaskGenerator.generate_task_variant(template_dict)
        print('Сгенерированный вариант:', variant, type(variant))
        
        return jsonify(variant)
    except Exception as e:
        print('Ошибка генерации задания:', e)
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# В app.py добавляем новые маршруты и изменяем существующие

@app.route('/teacher/lesson_templates')
def manage_lesson_templates():
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))
    
    conn = get_db()
    try:
        # Получаем все учебники для выбора шаблонов
        textbooks = conn.execute('SELECT * FROM textbooks ORDER BY grade, title').fetchall()
        return render_template('lesson_templates.html',
                            full_name=session['full_name'],
                            textbooks=textbooks)
    except Exception as e:
        print(f"Error: {e}")
        return "Произошла ошибка", 500
    finally:
        conn.close()

@app.route('/api/lesson_templates', methods=['POST'])
def save_lesson_template():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    required_fields = ['name', 'question_template', 'answer_template', 'parameters']
    
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = get_db()
    try:
        # Сохраняем шаблон для урока (без привязки к учебнику)
        conn.execute('''
            INSERT INTO lesson_templates 
            (name, question_template, answer_template, parameters)
            VALUES (%s, %s, %s, %s)
        ''', (
            data['name'],
            data['question_template'],
            data['answer_template'],
            json.dumps(data['parameters'])
        ))
        
        conn.commit()
        return jsonify({
            'success': True,
            'template_id': conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        })
    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        conn.close()

@app.route('/api/lesson_templates/<int:template_id>')
def get_lesson_template(template_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        template = conn.execute('''
            SELECT * FROM lesson_templates WHERE id = %s
        ''', (template_id,)).fetchone()

        if not template:
            return jsonify({'error': 'Template not found'}), 404

        return jsonify({
            'success': True,
            'template': dict(template)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/teacher/bulk_delete_templates', methods=['POST'])
def bulk_delete_templates():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    textbook_id = data['textbook_id']
    template_ids = data['template_ids']
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Удаляем только шаблоны, принадлежащие указанному учебнику
        placeholders = ','.join(['%s'] * len(template_ids))
        cursor.execute(f'''
            DELETE FROM task_templates 
            WHERE id IN ({placeholders}) AND textbook_id = %s
        ''', (*template_ids, textbook_id))
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count
        })
    except Exception as e:
        conn.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        conn.close()

def float_to_fraction(val, max_denominator=1000):
    """Преобразует float в несократимую обыкновенную дробь."""
    frac = Fraction(val).limit_denominator(max_denominator)
    return f"{frac.numerator}/{frac.denominator}"
                


@app.route('/api/generate_homework/<int:lesson_id>/<int:student_id>', methods=['POST'])
def generate_homework(lesson_id, student_id):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Получаем ответы ученика
    cursor.execute('''
        SELECT t.question, sa.answer, sa.is_correct, v.variant_data
        FROM student_answers sa
        JOIN lesson_tasks t ON t.id = sa.task_id
        LEFT JOIN student_task_variants v ON v.task_id = t.id AND v.user_id = sa.user_id
        WHERE sa.user_id = %s AND t.lesson_id = %s
    ''', (student_id, lesson_id))

    rows = cursor.fetchall()
    if not rows:
        return jsonify({'error': 'Нет ответов'}), 404

    # ← НОВОЕ: узнаём номер класса урока
    cursor.execute("""
        SELECT c.grade
        FROM lessons l
        JOIN classes c ON l.class_id = c.id
        WHERE l.id = %s
    """, (lesson_id,))
    row_grade = cursor.fetchone()
    grade = row_grade['grade'] if row_grade else "неизвестный"

    wrong_data = ""
    for row in rows:
        if not row['is_correct']:
            variant = json.loads(row['variant_data']) if row['variant_data'] else {}
            question = variant.get('generated_question', row['question'])
            answer = row['answer']
            correct_answer = variant.get('computed_answer', 'неизвестно')
            wrong_data += f"{question} = {answer} ❌ (нужно: {correct_answer})\n"

    if not wrong_data:
        return jsonify({'text': 'Ученик не допустил ошибок. ДЗ не требуется.'})

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # ← ПРОМПТ тот же, только добавлена одна строка с классом
    prompt = rf"""
Это ученик {grade} класса (российская школа). Объясняй на уровне этого класса.

Ученик сделал ошибки:

{wrong_data}

Составь домашнее задание по следующей структуре:

1. Вступление. Обратись к ученику добрым тоном. Объясни, какие ошибки он допустил, и что мы сейчас разберём вместе.

2. Для каждой задачи с ошибкой:
    - Покажи саму задачу и ответ ученика
    - Объясни, в чём ошибка (на понятном языке). И разбери ошибку подробно, по шагам. 
    - Разбери аналогичный пример с пошаговым объяснением (без использования LaTeX)
    - Дай 1 новое похожее задание без решения

3. Заверши поддержкой и мотивацией (например: "У тебя точно получится!").

Форматируй красиво: заголовки **жирным**, задачи в блоках, шаги с отступами. Не используй \[ \] или \( \) — формулы пиши текстом.
"""

    chat_response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    content = chat_response.choices[0].message.content

    rendered = render_template("homework_template.html", content=content)
    filepath = f"homeworks/homework_{lesson_id}_{student_id}.pdf"
    os.makedirs("homeworks", exist_ok=True)
    HTML(string=rendered).write_pdf(filepath)

    return jsonify({'url': f"/{filepath}"})

@app.route('/homeworks/<path:filename>')
def serve_homework(filename):
    return send_from_directory('homeworks', filename)
               
@app.route('/api/generate_homework_class/<int:lesson_id>', methods=['POST'])
def generate_homework_class(lesson_id):
    print("Генерация ДЗ для класса, lesson_id:", lesson_id)
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Получаем всех учеников класса
    cursor.execute('''
        SELECT u.id, u.full_name
        FROM users u
        JOIN lessons l ON u.class_id = l.class_id
        WHERE l.id = %s AND u.role = 'student'
        ORDER BY u.full_name
    ''', (lesson_id,))
    students = cursor.fetchall()

    if not students:
        return jsonify({'error': 'Нет учеников в классе'}), 404

    # Собираем индивидуальные отчеты
    homework_blocks = []
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    for student in students:
        print("Обрабатываю ученика:", student)
        student_id = student['id']
        full_name = student['full_name']

        # Получаем ошибки по аналогии с generate_homework
        cursor.execute('''
            SELECT t.id as task_id, t.question, sa.answer, sa.is_correct, v.variant_data
            FROM lesson_tasks t
            LEFT JOIN student_answers sa ON sa.task_id = t.id AND sa.user_id = %s
            LEFT JOIN student_task_variants v ON v.task_id = t.id AND v.user_id = %s
            WHERE t.lesson_id = %s
        ''', (student_id, student_id, lesson_id))
        rows = cursor.fetchall()
        print("Ответы ученика:", rows)

        wrong_data = ""
        data = request.get_json(silent=True) or {}
        exclude = set(str(x) for x in data.get("exclude", []))

        wrong_data = ""
        for row in rows:
            if (row['is_correct'] == False or row['answer'] is None) and str(row['task_id']) not in exclude:
                variant = json.loads(row['variant_data']) if row['variant_data'] else {}
                question = variant.get('generated_question', row['question'])
                answer = row['answer'] if row['answer'] is not None else "—"
                correct_answer = variant.get('computed_answer', 'неизвестно')
                wrong_data += f"{question} = {answer} ❌ (нужно: {correct_answer})\n"
        print("wrong_data:", wrong_data)

        if not wrong_data:
            # Если нет ошибок — похвала
            student_hw = f"<h2>Домашка для {full_name}</h2>\n<p>Молодец! Ошибок нет — так держать 🎉</p>"
        else:
            prompt = rf"""
Ты — дружелюбный учитель. Проанализируй ошибки ученика и создай индивидуальное домашнее задание в Markdown-формате по структуре:

# Домашнее задание для {full_name}

Вот ошибки ученика:
{wrong_data}

Краткое приветствие и мотивация.

## Задача 1

**Условие:** ...  
**Ответ ученика:** ...  
**Правильный ответ:** ...  

**В чём ошибка:**  
Объясни кратко.

**Как решать:**
1. Шаг 1...
2. Шаг 2...

**Аналогичный пример:**
Пошаговое объяснение похожей задачи.

**Новые задания:**
- Задание 1
- Задание 2

## Задача 2
(и так далее...)

В конце — мотивация и пожелание удачи.

**Важно:**
- Используй Markdown (`#`, `##`, `**` для выделения, списки).
- Между логическими блоками делай пустые строки.
- Не вставляй формулы в виде LaTeX или кода! Дроби пиши через слэш (например, 3 1/2).
"""
            chat_response = client.chat.completions.create(
                model="gpt-4.1-mini",  # или другая твоя модель
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            hw_text = chat_response.choices[0].message.content
            hw_html = markdown.markdown(hw_text, extensions=['extra', 'nl2br', 'sane_lists'])
            student_hw = f"<div style='page-break-before: always'></div><h2>Домашка для {full_name}</h2>\n{hw_html}"

        homework_blocks.append(student_hw)

    # Собираем единый HTML и рендерим PDF
    html = render_template('homework_class_template.html', blocks=homework_blocks)
    filepath = f"homeworks/homework_class_{lesson_id}.pdf"
    os.makedirs("homeworks", exist_ok=True)
    HTML(string=html).write_pdf(filepath)

    # Отдаем PDF
    return send_from_directory('homeworks', f"homework_class_{lesson_id}.pdf", as_attachment=True)

@app.route('/teacher/set_grade', methods=['POST'])
def set_grade():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    student_id = data.get('student_id')
    grade = data.get('grade')

    if grade not in [2, 3, 4, 5]:
        return jsonify({'error': 'Invalid grade'}), 400

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute('''
            UPDATE users SET grade = %s WHERE id = %s AND role = 'student'
        ''', (grade, student_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()


import openai

@app.route('/api/ai_step_dialog', methods=['POST'])
def ai_step_dialog():
    data = request.get_json()
    user_id = data.get("user_id")
    question = data.get("question")
    history = data.get("history", [])

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT grade FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    if row and row["grade"] is not None:
        mark = int(row["grade"])
        if mark in (4, 5):
            # Для сильных учеников — не давать ИИ-подсказки
            return jsonify({
                "question": "",
                "options": [],
                "correct_index": None,
                "explanation": ""
            })
        elif mark == 2:
            student_level = "weak"
        elif mark == 3:
            student_level = "medium"
        else:
            student_level = "medium"
    else:
        student_level = "medium"

    level_text = {
        "weak": "Ученик часто ошибается и слабо понимает материал. Пиши максимально просто, шаг за шагом.",
        "medium": "Ученик иногда ошибается, объясняй достаточно подробно, но не слишком просто.",
        "strong": "Ученик хорошо разбирается, можно предлагать более сложные варианты, минимум пояснений."
    }[student_level]

    # --- Формируем промпт для OpenAI ---
    prompt = f"""
    Ты — доброжелательный репетитор математики. Ученик только что ошибся в задании "{question}".
    {level_text}
    Сгенерируй следующий шаг пошагового мини-квеста для обучения:
    1. Придумай понятный вопрос (коротко), который побуждает подумать, что делать дальше по решению задачи.
    2. Дай 2-4 варианта ответа. Только один из них должен быть правильным.
    3. Укажи, какой индекс правильного варианта.
    4. Объясни (кратко и понятно!), почему этот шаг верный или что стоит сделать.
    Формат строго:
    {{
        "question": "...",
        "options": ["...", "...", "..."],
        "correct_index": 1,
        "explanation": "..."
    }}
    Уровень ученика: {student_level}.
    История шагов: {history if history else "шаг первый, начало решения"}
    Не объясняй полностью, а только следующий шаг!
    """

    # --- Запрос к OpenAI ---
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",  # Или другой твой доступный
            messages=[{"role": "user", "content": prompt}],
            max_tokens=350,
            temperature=0.3
        )
        # Парсим json из ответа
        import json
        content = response.choices[0].message.content
        # Иногда GPT оборачивает в ```
        content = content.replace('```json', '').replace('```', '').strip()
        data = json.loads(content)
        return jsonify(data)
    except Exception as e:
        print("Ошибка OpenAI:", e)
        return jsonify({'error': str(e)}), 500

    
@app.route('/api/ai_full_solution', methods=['POST'])
def ai_full_solution():
    data = request.get_json() or {}

    # --- данные запроса ---
    task_id = data.get("task_id")
    user_id = data.get("user_id") or session.get("user_id")
    question = data.get("question", "") or ""
    student_grade = data.get("student_grade", data.get("grade", 5))
    student_answer = (data.get("student_answer") or "").strip()

    # --- хеш вопроса (важно для "перерешать ещё раз") ---
    question_hash = hashlib.sha256(question.strip().encode("utf-8")).hexdigest()

    # =====================================================
    # 🔹 0. ПРОВЕРКА КЕША УРОВНЯ ЗАДАНИЯ (lesson_tasks.ai_solution)
    # Только для фото-заданий и статичных заданий (template_id IS NULL).
    # Для шаблонных заданий с вариантами — кэш по (user_id, task_id, question_hash).
    # =====================================================
    photo_path = None
    template_id = None
    if task_id:
        conn = get_db()
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(
                "SELECT photo_path, template_id, ai_solution FROM lesson_tasks WHERE id = %s",
                (task_id,)
            )
            lt_row = cursor.fetchone()
            if lt_row:
                photo_path = lt_row['photo_path']
                template_id = lt_row['template_id']
                # Кэш уровня задания только для статичных/фото-заданий
                if template_id is None and lt_row['ai_solution']:
                    try:
                        cached = json.loads(lt_row['ai_solution'])
                        return jsonify({
                            "solution": cached.get("solution", ""),
                            "ai_verdict": cached.get("ai_verdict"),
                            "cached": True
                        })
                    except Exception:
                        pass
        finally:
            conn.close()

    # =====================================================
    # 🔹 1. ПРОВЕРКА КЕША ПОЛЬЗОВАТЕЛЯ (не старше 4 дней)
    # =====================================================
    if user_id and task_id:
        conn = get_db()
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("""
    SELECT solution_text, ai_verdict
    FROM ai_solution_cache
    WHERE user_id = %s
      AND task_id = %s
      AND question_hash = %s
      AND school_id = %s
      AND created_at >= NOW() - INTERVAL '4 days'
    ORDER BY created_at DESC
    LIMIT 1
""", (user_id, task_id, question_hash, g.school_id))

            row = cursor.fetchone()

            if row:
                return jsonify({
                    "solution": row["solution_text"],
                    "ai_verdict": row["ai_verdict"],
                    "cached": True
                })
        finally:
            conn.close()

    # =====================================================
    # 🔹 2. ФОРМИРОВАНИЕ ПРОМПТА
    # =====================================================
    if photo_path and not question.strip():
        prompt = f"""
Ты — преподаватель математики в российской школе. Учитывай пожалуйста русский ход решения, а не американский и т.д.
Дай пошаговое объяснение решения задачи для ученика {student_grade} класса.
Ты объясняешь материал в духе школьных учебников и методических пособий Минпросвещения РФ, но без заумных определений.
На изображении представлена математическая задача. Реши её.

ТРЕБОВАНИЯ К ОТВЕТУ (ОЧЕНЬ ВАЖНО):

1️⃣ СНАЧАЛА выведи раздел "РЕШЕНИЕ:"
— только математические действия
— без слов и комментариев
— как запись в тетради

2️⃣ ПОТОМ выведи раздел "ПОЯСНЕНИЕ:"

Дай пошаговое объяснение, чтобы ученик понял ход рассуждений.
В конце обязательно укажи правильный ответ.
Не упоминай, что ты ИИ.
Все математические формулы оформляй в LaTeX.
Не используй одинарные квадратные скобки [ ... ] для формул.

ВАЖНО:
1) В самом конце (последней строкой) выведи JSON без markdown и без ``` вида:
{{"final_answer":"...","is_student_correct":true/false}}
2) final_answer — это итоговый ответ по твоему решению (строкой).
3) is_student_correct сравнивает final_answer с ответом ученика: "{student_answer}".
Сравнение делай по смыслу (эквивалентность выражений, степени, дроби), а не только по точному совпадению строк.
"""
    else:
        prompt = f"""
Ты — преподаватель математики в российской школе. Учитывай пожалуйста русский ход решения, а не американский и т.д.
Дай пошаговое объяснение решения задачи для ученика {student_grade} класса.
Ты объясняешь материал в духе школьных учебников и методических пособий Минпросвещения РФ, но без заумных определений.
Задача:
"{question}"

ТРЕБОВАНИЯ К ОТВЕТУ (ОЧЕНЬ ВАЖНО):

1️⃣ СНАЧАЛА выведи раздел "РЕШЕНИЕ:"
— только математические действия
— без слов и комментариев
— как запись в тетради

2️⃣ ПОТОМ выведи раздел "ПОЯСНЕНИЕ:"

Дай пошаговое объяснение, чтобы ученик понял ход рассуждений.
В конце обязательно укажи правильный ответ.
Не упоминай, что ты ИИ.
Все математические формулы оформляй в LaTeX.
Не используй одинарные квадратные скобки [ ... ] для формул.

ВАЖНО:
1) В самом конце (последней строкой) выведи JSON без markdown и без ``` вида:
{{"final_answer":"...","is_student_correct":true/false}}
2) final_answer — это итоговый ответ по твоему решению (строкой).
3) is_student_correct сравнивает final_answer с ответом ученика: "{student_answer}".
Сравнение делай по смыслу (эквивалентность выражений, степени, дроби), а не только по точному совпадению строк.
"""

    # =====================================================
    # 🔹 3. ЗАПРОС К OPENAI
    # =====================================================
    try:
        if photo_path:
            # Vision-режим: отправляем фото + текст
            if photo_path.startswith('http'):
                # Внешний URL — передаём напрямую
                image_url = photo_path
            else:
                # Локальный файл — кодируем в base64
                import base64
                full_img_path = os.path.join(os.path.dirname(__file__), photo_path.lstrip('/'))
                with open(full_img_path, 'rb') as img_file:
                    image_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                image_url = f"data:image/jpeg;base64,{image_base64}"
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                                "detail": "high"
                            }
                        }
                    ]
                }],
                max_tokens=3000,
                temperature=0.2
            )
        else:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.2
            )

        content = response.choices[0].message.content or ""

        ai_verdict = None
        solution_text = content

        # --- ищем JSON в конце ---
        json_blocks = re.findall(
            r'\{[^{}]*"final_answer"\s*:\s*".*?"[^{}]*"is_student_correct"\s*:\s*(?:true|false)[^{}]*\}',
            content,
            flags=re.DOTALL | re.IGNORECASE
        )

        if json_blocks:
            last_json = json_blocks[-1]
            try:
                ai_verdict = json.loads(last_json)
                solution_text = content.replace(last_json, "").strip()
            except Exception:
                ai_verdict = None

        # =====================================================
        # 🔹 4. СОХРАНЕНИЕ В КЕШ ЗАДАНИЯ (lesson_tasks.ai_solution)
        # Только для статичных/фото-заданий (template_id IS NULL).
        # Шаблонные задания кэшируются только в ai_solution_cache по question_hash.
        # =====================================================
        if task_id and template_id is None:
            conn = get_db()
            try:
                cursor = conn.cursor()
                cursor.execute("""
    UPDATE lesson_tasks
    SET ai_solution = %s,
        ai_solution_created_at = CURRENT_TIMESTAMP
    WHERE id = %s
""", (
    json.dumps({"solution": solution_text, "ai_verdict": ai_verdict}),
    task_id
))
                conn.commit()
            finally:
                conn.close()

        # =====================================================
        # 🔹 5. СОХРАНЕНИЕ В КЕШ ПОЛЬЗОВАТЕЛЯ
        # =====================================================
        if user_id and task_id:
            conn = get_db()
            try:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute("""
    INSERT INTO ai_solution_cache
        (user_id, task_id, question_hash, solution_text, ai_verdict, school_id)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id, task_id, question_hash)
    DO UPDATE SET
        solution_text = EXCLUDED.solution_text,
        ai_verdict = EXCLUDED.ai_verdict,
        school_id = EXCLUDED.school_id,
        created_at = CURRENT_TIMESTAMP
""", (
    user_id,
    task_id,
    question_hash,
    solution_text,
    json.dumps(ai_verdict) if ai_verdict else None,
    g.school_id
))

                conn.commit()
            finally:
                conn.close()

        return jsonify({
            "solution": solution_text,
            "ai_verdict": ai_verdict,
            "cached": False
        })

    except Exception as e:
        print("Ошибка OpenAI:", e)
        return jsonify({
            "solution": "Ошибка при получении решения от ИИ.",
            "ai_verdict": None,
            "error": str(e)
        }), 500




@app.route('/dispute_answer', methods=['POST'])
def dispute_answer():
    data = request.get_json()
    task_id = data.get("task_id")
    student_answer = data.get("answer", "").strip()
    correct_answer = data.get("correct_answer", "").strip()

    if student_answer == correct_answer:
        user_id = session.get("user_id")

        try:
            # Отправляем на /save_answer
            requests.post("http://127.0.0.1:5000/save_answer", json={
                "task_id": task_id,
                "answer": student_answer,
                "is_correct": True,
                "user_id": user_id
            })
        except Exception as e:
            print("Ошибка при сохранении через /save_answer:", e)

        return jsonify({"result": "accepted", "message": "Ответ засчитан как правильный."})
    else:
        return jsonify({"result": "rejected", "message": "Ответ действительно отличается."})


def infer_student_mark(user_id: int) -> int:
    """
    Сначала пробуем явную оценку из users.grade (2..5).
    Если её нет — оцениваем по истории ответов.
    """
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 1. Проверяем поле grade у пользователя
        cur.execute("SELECT grade FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if row and row["grade"] in (2, 3, 4, 5):
            return int(row["grade"])

        # 2. Если grade не задано — fallback на статистику
        cur.execute("""
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN is_correct AND NOT COALESCE(retry_used, FALSE) THEN 1 ELSE 0 END) +
                SUM(CASE WHEN is_correct AND COALESCE(retry_used, FALSE) THEN 0.5 ELSE 0 END) AS correct
            FROM student_answers
            WHERE user_id = %s
        """, (user_id,))
        row = cur.fetchone()
        total = row['total'] or 0
        correct = row['correct'] or 0
        if total == 0:
            return 3
        rate = correct / total
        if rate < 0.25:
            return 2
        elif rate < 0.50:
            return 3
        elif rate < 0.75:
            return 4
        else:
            return 5
    finally:
        conn.close()

@app.route('/api/generate_retry_task/<int:task_id>')
def generate_retry_task(task_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    conn = get_db()

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 1. Получаем задачу и шаблон
        cursor.execute('''
            SELECT
                lt.lesson_id,
                lt.template_id,
                tt.question_template,
                tt.answer_template,
                tt.parameters,
                tt.conditions,
                tt.answer_type
            FROM lesson_tasks lt
            LEFT JOIN task_templates tt ON lt.template_id = tt.id
            WHERE lt.id = %s
              AND lt.school_id = %s
        ''', (task_id, g.school_id))

        task = cursor.fetchone()
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        if not task['template_id']:
            return jsonify({'error': 'Для этого задания нет template_id'}), 400

        # 2. Получаем уже выданный ученику основной вариант
        cursor.execute('''
            SELECT variant_data
            FROM student_task_variants
            WHERE lesson_id = %s
              AND user_id = %s
              AND task_id = %s
              AND school_id = %s
        ''', (task['lesson_id'], user_id, task_id, g.school_id))

        saved_variant_row = cursor.fetchone()
        if not saved_variant_row:
            return jsonify({'error': 'Исходный вариант ученика не найден'}), 404

        raw_variant = saved_variant_row['variant_data']
        if isinstance(raw_variant, str):
            try:
                saved_variant = json.loads(raw_variant)
            except Exception:
                saved_variant = {}
        else:
            saved_variant = raw_variant or {}

        # 3. Подготавливаем template_dict
        params = task['parameters']
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        elif not isinstance(params, dict):
            params = {}

        template_dict = {
            'id': task['template_id'],
            'question_template': task['question_template'],
            'answer_template': task['answer_template'],
            'parameters': params,
            'conditions': task['conditions'] or '',
            'answer_type': task['answer_type'] or 'numeric'
        }

        # 4. Генерируем полностью новый случайный вариант
        student_mark = infer_student_mark(user_id)
        variant = TaskGenerator.generate_task_variant(template_dict, band=student_mark)

        if not variant:
            return jsonify({'error': 'Не удалось сгенерировать retry-вариант'}), 500

        # 5. Сохраняем retry поверх предыдущего (каждый раз новый)
        saved_variant['retry_generated_question'] = variant['question']
        saved_variant['retry_computed_answer'] = variant['correct_answer']
        saved_variant['retry_params'] = variant['params']
        saved_variant['retry_choice_idx'] = variant.get('choice_idx')

        cursor.execute('''
            UPDATE student_task_variants
            SET variant_data = %s,
                created_at = CURRENT_TIMESTAMP
            WHERE lesson_id = %s
              AND user_id = %s
              AND task_id = %s
              AND school_id = %s
        ''', (
            json.dumps(saved_variant),
            task['lesson_id'],
            user_id,
            task_id,
            g.school_id
        ))

        conn.commit()

        return jsonify({
            'question': variant['question'],
            'correct_answer': variant['correct_answer'],
            'params': variant['params'],
            'choice_idx': variant.get('choice_idx')
        })

    except Exception as e:
        conn.rollback()
        print(f"Error in generate_retry_task: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/student/profile')
def student_profile():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Берём все уроки класса ученика
    cursor.execute('''
        SELECT l.id, l.title, l.date
        FROM lessons l
        JOIN users u ON l.class_id = u.class_id
        WHERE u.id = %s
        ORDER BY l.date DESC
    ''', (user_id,))
    lessons = cursor.fetchall()

    result = []
    for lesson in lessons:
        lesson_id = lesson['id']

        # Сколько заданий в уроке всего
        cursor.execute('SELECT COUNT(*) FROM lesson_tasks WHERE lesson_id = %s', (lesson_id,))
        total_tasks = cursor.fetchone()[0] or 0

        # Сколько заданий решено учеником
        cursor.execute('''
            SELECT COUNT(*) 
            FROM student_answers sa
            JOIN lesson_tasks lt ON sa.task_id = lt.id
            WHERE lt.lesson_id = %s AND sa.user_id = %s
        ''', (lesson_id, user_id))
        solved_tasks = cursor.fetchone()[0] or 0

        # Сколько решено правильно (без retry)
        cursor.execute('''
            SELECT COUNT(*)
            FROM student_answers sa
            JOIN lesson_tasks lt ON sa.task_id = lt.id
            WHERE lt.lesson_id = %s AND sa.user_id = %s AND sa.is_correct = TRUE AND NOT COALESCE(sa.retry_used, FALSE)
        ''', (lesson_id, user_id))
        correct_tasks = cursor.fetchone()[0] or 0

        # Сколько решено с ошибкой (partial)
        cursor.execute('''
            SELECT COUNT(*)
            FROM student_answers sa
            JOIN lesson_tasks lt ON sa.task_id = lt.id
            WHERE lt.lesson_id = %s AND sa.user_id = %s AND sa.is_correct = TRUE AND COALESCE(sa.retry_used, FALSE)
        ''', (lesson_id, user_id))
        partial_tasks = cursor.fetchone()[0] or 0

        incorrect_tasks = total_tasks - correct_tasks - partial_tasks

        result.append({
            'id': lesson['id'],
            'title': lesson['title'],
            'date': lesson['date'],
            'total_tasks': total_tasks,
            'correct_tasks': correct_tasks,
            'partial_tasks': partial_tasks,
            'incorrect_tasks': incorrect_tasks
        })

    conn.close()

    return render_template('student_profile.html',
                           full_name=session['full_name'],
                           lessons=result)



@app.route('/student/retry/<int:lesson_id>')
def student_retry_lesson(lesson_id):
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # 1. Выбираем шаблоны для всех задач, где есть ошибки
    cursor.execute('''
        SELECT
            lt.id AS task_id,
            lt.template_id,
            tt.question_template,
            tt.answer_template,
            tt.parameters,
            tt.conditions,
            tt.answer_type,
            stv.variant_data
        FROM lesson_tasks lt
        JOIN task_templates tt ON lt.template_id = tt.id
        LEFT JOIN student_answers sa
            ON sa.task_id = lt.id
        AND sa.user_id = %s
        AND sa.school_id = %s
        LEFT JOIN student_task_variants stv
            ON stv.lesson_id = lt.lesson_id
        AND stv.task_id = lt.id
        AND stv.user_id = %s
        AND stv.school_id = %s
        WHERE lt.lesson_id = %s
        AND lt.school_id = %s
        AND (sa.is_correct = FALSE OR sa.answer IS NULL)
    ''', (user_id, g.school_id, user_id, g.school_id, lesson_id, g.school_id))
    tasks = cursor.fetchall()

    if not tasks:
        conn.close()
        return render_template(
            'student_retry.html',
            tasks=[],
            user_id=user_id,
            lesson_title=f"Урок {lesson_id}"
        )

    generated_tasks = []
    for t in tasks:
        
        try:
            params = json.loads(t['parameters']) if isinstance(t['parameters'], str) else (t['parameters'] or {})

            template_dict = {
                'id': t['template_id'],
                'question_template': t['question_template'],
                'answer_template': t['answer_template'],
                'parameters': params,
                'conditions': t['conditions'] or '',
                'answer_type': t['answer_type'] or 'numeric'
            }

            # 1. Читаем старый variant_data
            raw_variant_data = t['variant_data']
            if isinstance(raw_variant_data, str):
                try:
                    old_variant_data = json.loads(raw_variant_data)
                except Exception:
                    old_variant_data = {}
            else:
                old_variant_data = raw_variant_data or {}

            initial_choice_idx = old_variant_data.get('initial_choice_idx')

            if initial_choice_idx is None:
                print(f"У задания {t['task_id']} нет initial_choice_idx, пропускаю")
                continue

            initial_choice_idx = int(initial_choice_idx)

            # 2. Считаем парный retry-вариант на основе реальной длины choice-массива
            choice_keys = [k for k, v in params.items() if isinstance(v, dict) and v.get('type') == 'choice']
            if choice_keys:
                choice_len = len(params[choice_keys[0]]['values'])
                retry_idx = (initial_choice_idx + choice_len // 2) % choice_len
            else:
                retry_idx = initial_choice_idx

            # 3. Генерируем НЕ случайный вариант, а строго нужный
            variant = TaskGenerator.generate_task_variant(
                template_dict,
                forced_choice_idx=retry_idx
            )

            generated_tasks.append({
                'id': t['task_id'],
                'template_id': t['template_id'],
                'question': variant['question'],
                'answer': variant['correct_answer']
            })

            # 4. Сохраняем новый retry-вариант
            new_variant_data = {
                'params': variant['params'],
                'generated_question': variant['question'],
                'computed_answer': variant['correct_answer'],
                'initial_choice_idx': initial_choice_idx,
                'current_choice_idx': retry_idx,
                'is_retry': True
            }

            cursor.execute('''
                INSERT INTO student_task_variants
                    (lesson_id, user_id, task_id, variant_data, school_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (lesson_id, user_id, task_id)
                DO UPDATE SET
                    variant_data = EXCLUDED.variant_data,
                    school_id = EXCLUDED.school_id,
                    created_at = CURRENT_TIMESTAMP
            ''', (
                lesson_id,
                user_id,
                t['task_id'],
                json.dumps(new_variant_data),
                g.school_id
            ))

        except Exception as e:
            print(f"Ошибка генерации задания {t['task_id']}: {e}")

    conn.commit()
    conn.close()

    # Получаем название урока
    lesson_title = f"Урок {lesson_id}"
    return render_template(
        'student_retry.html',
        tasks=generated_tasks,
        user_id=user_id,
        lesson_title=lesson_title
    )




@app.route('/student/statistics')
def student_statistics():
    if 'user_id' not in session or session['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('''
        SELECT 
            COUNT(sa.task_id) AS total_answers,
            SUM(CASE WHEN sa.is_correct AND NOT COALESCE(sa.retry_used, FALSE) THEN 1 ELSE 0 END) AS correct_answers,
            SUM(CASE WHEN sa.is_correct AND COALESCE(sa.retry_used, FALSE) THEN 1 ELSE 0 END) AS partial_answers,
            SUM(CASE WHEN NOT sa.is_correct THEN 1 ELSE 0 END) AS incorrect_answers
        FROM student_answers sa
        WHERE sa.user_id = %s
    ''', (user_id,))
    stats = cursor.fetchone()
    conn.close()
    return jsonify(dict(stats))


@app.route('/student/class_rating')
def student_class_rating():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute('SELECT class_id FROM users WHERE id = %s', (user_id,))
    class_row = cursor.fetchone()
    if not class_row:
        conn.close()
        return "Класс не найден", 404

    class_id = class_row['class_id']

    cursor.execute('''
        SELECT 
            u.id AS user_id,
            u.full_name,
            COUNT(sa.task_id) AS total,
            SUM(CASE WHEN sa.is_correct AND NOT COALESCE(sa.retry_used, FALSE) THEN 1 ELSE 0 END) AS correct,
            SUM(CASE WHEN sa.is_correct AND COALESCE(sa.retry_used, FALSE) THEN 1 ELSE 0 END) AS partial,
            ROUND(
                COALESCE(
                    ((SUM(CASE WHEN sa.is_correct AND NOT COALESCE(sa.retry_used, FALSE) THEN 1 ELSE 0 END) +
                      SUM(CASE WHEN sa.is_correct AND COALESCE(sa.retry_used, FALSE) THEN 0.5 ELSE 0 END))::numeric /
                     NULLIF(COUNT(sa.task_id), 0)::numeric) * 100,
                    0
                ), 1
            ) AS percent
        FROM users u
        LEFT JOIN student_answers sa ON sa.user_id = u.id
        WHERE u.class_id = %s AND u.role = 'student'
        GROUP BY u.id
        ORDER BY percent DESC, u.full_name
    ''', (class_id,))

    rating = cursor.fetchall()
    conn.close()

    return render_template('student_class_rating.html', rating=rating, user_id=user_id)


@app.route('/student/lesson_rating/<int:lesson_id>')
def student_lesson_rating(lesson_id):
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Определяем класс ученика
    cursor.execute('SELECT class_id FROM users WHERE id = %s', (user_id,))
    class_id = cursor.fetchone()['class_id']

    # Рейтинг по конкретному уроку
    cursor.execute('''
        SELECT 
            u.id AS user_id,
            u.full_name,
            COUNT(sa.task_id) AS total,
            SUM(CASE WHEN sa.is_correct AND NOT COALESCE(sa.retry_used, FALSE) THEN 1 ELSE 0 END) AS correct,
            SUM(CASE WHEN sa.is_correct AND COALESCE(sa.retry_used, FALSE) THEN 1 ELSE 0 END) AS partial,
            ROUND(
                COALESCE(
                    ((SUM(CASE WHEN sa.is_correct AND NOT COALESCE(sa.retry_used, FALSE) THEN 1 ELSE 0 END) +
                      SUM(CASE WHEN sa.is_correct AND COALESCE(sa.retry_used, FALSE) THEN 0.5 ELSE 0 END))::numeric /
                     NULLIF(COUNT(sa.task_id), 0)::numeric) * 100,
                    0
                ), 1
            ) AS percent
        FROM users u
        JOIN student_answers sa ON sa.user_id = u.id
        JOIN lesson_tasks lt ON sa.task_id = lt.id
        WHERE u.class_id = %s AND lt.lesson_id = %s
        GROUP BY u.id
        ORDER BY percent DESC, u.full_name
    ''', (class_id, lesson_id))

    rating = cursor.fetchall()
    conn.close()

    return render_template('student_class_rating.html', rating=rating, user_id=user_id)



@app.route('/api/ai_tutor_dialog', methods=['POST'])
def ai_tutor_dialog():
    data = request.get_json()
    task_id = data.get("task_id")
    question = data.get("question", "")
    history = data.get("history", [])
    
    # Формируем контекст: сначала системную инструкцию, затем описание задачи
    system_prompt = (
        "Ты — терпеливый и доброжелательный учитель математики в российской школе. "
        "Помогай ученику разобраться в задаче, но не давай сразу правильный ответ. "
        "Твоя цель — наводить на правильные мысли, поддерживать, объяснять шаг за шагом, "
        "как на уроке с пятиклассником или семиклассником. "
        "Если ученик ошибается, мягко подскажи, где ошибка, предложи подумать ещё. "
        "Говори просто, дружелюбно, по-русски, избегай сухих формулировок."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Вот задача, которую решает ученик:\n{question}"}
    ]

    # Добавляем историю диалога
    messages.extend(history)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8,
            max_tokens=600
        )
        reply = response.choices[0].message.content
        return jsonify({"reply": reply})
    except Exception as e:
        print("Ошибка в ai_tutor_dialog:", e)
        return jsonify({"reply": "Ошибка при получении ответа от ИИ."}), 500


@app.route("/dev/playground")
def dev_playground():
    return render_template("dev_playground.html")

from services.template_importer import import_templates_from_json

@app.route("/dev/import-templates", methods=["GET", "POST"])
def dev_import_templates():
    if 'user_id' not in session or session['role'] != 'teacher':
        return redirect(url_for("login"))

    result = None
    imported_names = []
    show_all = request.args.get('show_all', '0') == '1'

    if request.method == "POST":
        json_text = request.form.get("json", "")

        try:
            conn = get_db()
            ok, msg, imported_names = import_templates_from_json(conn, json_text)
            result = {"ok": ok, "msg": msg}
        except Exception as e:
            result = {
                "ok": False,
                "msg": f"Критическая ошибка сервера: {e}"
            }
        finally:
            conn.close()

    # Загружаем шаблоны для отображения
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        if imported_names and not show_all:
            # Показываем только что импортированные шаблоны
            cursor.execute("""
                SELECT tt.*, tb.title as textbook_title, tb.grade
                FROM task_templates tt
                LEFT JOIN textbooks tb ON tt.textbook_id = tb.id
                WHERE tt.school_id IS NULL
                  AND tt.name = ANY(%s)
                ORDER BY tt.textbook_id, tt.id
            """, (imported_names,))
        else:
            # Показываем все шаблоны
            cursor.execute("""
                SELECT tt.*, tb.title as textbook_title, tb.grade
                FROM task_templates tt
                LEFT JOIN textbooks tb ON tt.textbook_id = tb.id
                WHERE tt.school_id IS NULL
                ORDER BY tt.textbook_id, tt.id
            """)
        templates = cursor.fetchall()
    except Exception as e:
        templates = []
        if not result:
            result = {"ok": False, "msg": f"Ошибка загрузки шаблонов: {e}"}
    finally:
        conn.close()

    return render_template("dev_import_templates.html",
                           result=result,
                           templates=[dict(t) for t in templates],
                           show_all=show_all,
                           just_imported=bool(imported_names))


@app.route('/api/templates/<int:template_id>/photo', methods=['POST', 'DELETE'])
def template_photo(template_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        if request.method == 'DELETE':
            cursor.execute("""
                UPDATE task_templates SET photo_path = NULL WHERE id = %s
            """, (template_id,))
            conn.commit()
            return jsonify({"success": True})

        # POST — загрузка файла
        photo = request.files.get('photo')
        if not photo:
            return jsonify({"error": "No file"}), 400

        upload_dir = os.path.join('static', 'uploads', 'template_photos')
        os.makedirs(upload_dir, exist_ok=True)

        ext = os.path.splitext(secure_filename(photo.filename))[1] or '.jpg'
        filename = f"tpl_{template_id}_{int(time.time())}{ext}"
        filepath = os.path.join(upload_dir, filename)
        photo.save(filepath)

        photo_url = f"/static/uploads/template_photos/{filename}"
        cursor.execute("""
            UPDATE task_templates
            SET photo_path = %s,
                question_template = ''
            WHERE id = %s
        """, (photo_url, template_id))
        conn.commit()
        return jsonify({"success": True, "path": photo_url})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route('/api/lesson-tasks/<int:task_id>/photo', methods=['POST', 'DELETE'])
def lesson_task_photo(task_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        # Проверяем, что задание принадлежит учителю/школе
        cursor.execute("""
            SELECT lt.id FROM lesson_tasks lt
            JOIN lessons l ON lt.lesson_id = l.id
            WHERE lt.id = %s AND l.teacher_id = %s AND lt.school_id = %s
        """, (task_id, session['user_id'], g.school_id))
        if not cursor.fetchone():
            return jsonify({"error": "Task not found"}), 404

        if request.method == 'DELETE':
            cursor.execute("""
                UPDATE lesson_tasks SET photo_path = NULL WHERE id = %s
            """, (task_id,))
            conn.commit()
            return jsonify({"success": True})

        # POST — загрузка файла
        photo = request.files.get('photo')
        if not photo:
            return jsonify({"error": "No file"}), 400

        upload_dir = os.path.join('static', 'uploads', 'task_photos')
        os.makedirs(upload_dir, exist_ok=True)

        ext = os.path.splitext(secure_filename(photo.filename))[1] or '.jpg'
        filename = f"task_{task_id}_{int(time.time())}{ext}"
        filepath = os.path.join(upload_dir, filename)
        photo.save(filepath)

        photo_url = f"/static/uploads/task_photos/{filename}"
        cursor.execute("""
            UPDATE lesson_tasks
            SET photo_path = %s,
                question = ''
            WHERE id = %s
        """, (photo_url, task_id))
        conn.commit()
        return jsonify({"success": True, "path": photo_url})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route('/teacher/get_seating')
def get_seating():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    class_id = request.args.get('class_id')
    if not class_id:
        return jsonify({'seats': []})

    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
    SELECT student_id, seat_row, seat_col
    FROM public.student_seats
    WHERE class_id = %s AND school_id = %s
""", (class_id, g.school_id))

        rows = cur.fetchall()
        return jsonify({'seats': [dict(r) for r in rows]})
    finally:
        conn.close()

@app.route('/teacher/save_seating', methods=['POST'])
def save_seating():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    class_id = data.get('class_id')
    seats = data.get('seats', [])

    if not class_id or not isinstance(seats, list):
        return jsonify({'success': False, 'error': 'Invalid payload'}), 400

    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # удаляем старую рассадку класса и записываем новую
        cur.execute("DELETE FROM public.student_seats WHERE class_id = %s AND school_id = %s", (class_id, g.school_id))


        # вставляем новую
        for s in seats:
            cur.execute("""
    INSERT INTO public.student_seats (class_id, student_id, seat_row, seat_col, school_id)
    VALUES (%s, %s, %s, %s, %s)
""", (class_id, int(s['student_id']), int(s['seat_row']), int(s['seat_col']), g.school_id))


        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/teacher/update_student', methods=['POST'])
def update_student():
    if 'user_id' not in session or session.get('role') != 'teacher':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    data = request.get_json() or {}

    student_id = data.get('student_id')
    full_name = (data.get('full_name') or '').strip()
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not student_id or not full_name or not username:
        return jsonify({'success': False, 'error': 'Invalid data'}), 400

    conn = get_db()
    try:
        cur = conn.cursor()

        if password:
            cur.execute("""
                UPDATE users
                SET full_name = %s,
                    username = %s,
                    
                WHERE id = %s
            """, (full_name, username, password, student_id))
        else:
            cur.execute("""
                UPDATE users
                SET full_name = %s,
                    username = %s
                WHERE id = %s
            """, (full_name, username, student_id))

        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()



@app.route('/teacher/create_class', methods=['POST'])
def create_class():
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    grade = data.get('grade')
    letter = (data.get('letter') or '').strip().upper()

    if not grade or not letter:
        return jsonify({'success': False, 'error': 'Invalid data'}), 400

    conn = get_db()
    try:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO classes (grade, letter, school_id)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (int(grade), letter, g.school_id))

        class_id = cur.fetchone()[0]
        conn.commit()

        return jsonify({
            'success': True,
            'class': {
                'id': class_id,
                'grade': grade,
                'letter': letter
            }
        })
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({'success': False, 'error': 'Класс уже существует'}), 400
    finally:
        conn.close()


@app.route('/teacher/suggest_username', methods=['POST'])
def suggest_username():
    if session.get('role') != 'teacher':
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json()
    full_name = data.get('full_name', '').strip()

    if not full_name:
        return jsonify({}), 400

    conn = get_db()
    try:
        username = generate_unique_username(conn, full_name)
        return jsonify({'username': username})
    finally:
        conn.close()

@app.route('/teacher/get_lesson_seating/<int:lesson_id>')
def get_lesson_seating(lesson_id):

    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:

        # получаем класс урока
        cursor.execute("""
            SELECT class_id
            FROM lessons
            WHERE id = %s
        """, (lesson_id,))

        lesson = cursor.fetchone()

        if not lesson:
            return jsonify({'seats': []})

        class_id = lesson['class_id']

        # берём ТОЛЬКО:
        # 1) базовую рассадку класса
        # 2) гостей ЭТОГО урока
        cursor.execute("""
            SELECT
                u.full_name,
                ss.seat_row,
                ss.seat_col
            FROM student_seats ss
            JOIN users u ON u.id = ss.student_id
            WHERE ss.class_id = %s
            AND (
                (u.is_guest = FALSE AND ss.lesson_id IS NULL)  -- обычная рассадка класса
                OR
                (u.is_guest = TRUE AND ss.lesson_id = %s)      -- гости только этого урока
            )
            ORDER BY ss.seat_row, ss.seat_col
        """, (class_id, lesson_id))

        seats = cursor.fetchall()

        return jsonify({
            'seats': [dict(s) for s in seats]
        })

    finally:
        conn.close()

import random

def generate_room_code(conn):
    cursor = conn.cursor()

    while True:
        code = random.randint(100000, 999999)

        cursor.execute(
            "SELECT 1 FROM lessons WHERE room_code = %s",
            (code,)
        )

        if not cursor.fetchone():
            return code

@app.route('/join_code/<int:code>')
def join_by_code(code):

    conn = get_db()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("""
        SELECT join_token
        FROM lessons
        WHERE room_code = %s
    """, (code,))

    lesson = cursor.fetchone()

    conn.close()

    if not lesson:
        return "Урок не найден", 404

    return redirect(url_for('join_lesson', token=lesson['join_token']))


# =============================================================================
# DUEL / TOURNAMENT MODE API
# =============================================================================

def _json_safe(value):
    """Преобразует datetime в строки для JSON-сериализации."""
    import datetime
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_json_safe(v) for v in value]
    elif isinstance(value, datetime.datetime):
        return value.isoformat()
    return value

@app.route('/api/duel/<int:lesson_id>/rounds', methods=['GET'])
def get_duel_rounds(lesson_id):
    """Получить список раундов дуэли для урока."""
    if 'user_id' not in session or session['role'] not in ('teacher', 'student'):
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('''
            SELECT id, round_number, round_name, time_seconds, status, started_at, ended_at
            FROM duel_rounds
            WHERE lesson_id = %s
            ORDER BY round_number
        ''', (lesson_id,))
        rounds = [dict(r) for r in cursor.fetchall()]

        # Загружаем задания для каждого раунда
        for r in rounds:
            cursor.execute('''
                SELECT drt.task_id, lt.question, lt.answer, lt.template_id, lt.photo_path
                FROM duel_round_tasks drt
                JOIN lesson_tasks lt ON lt.id = drt.task_id
                WHERE drt.round_id = %s
                ORDER BY drt.position
            ''', (r['id'],))
            r['tasks'] = [dict(t) for t in cursor.fetchall()]

        return jsonify({'rounds': _json_safe(rounds)})
    finally:
        conn.close()


@app.route('/api/duel/<int:lesson_id>/rounds', methods=['POST'])
def create_duel_rounds(lesson_id):
    """Создать или пересоздать раунды дуэли в зависимости от числа участников."""
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Проверяем, что урок принадлежит учителю
        cursor.execute('''
            SELECT class_id FROM lessons
            WHERE id = %s AND teacher_id = %s AND school_id = %s
        ''', (lesson_id, session['user_id'], g.school_id))
        lesson = cursor.fetchone()
        if not lesson:
            return jsonify({'error': 'Lesson not found'}), 404

        # Считаем число учеников в классе
        cursor.execute('''
            SELECT COUNT(*) FROM users
            WHERE class_id = %s AND role = 'student' AND school_id = %s
        ''', (lesson['class_id'], g.school_id))
        student_count = cursor.fetchone()[0]

        # Удаляем старые раунды (каскадно удалит duel_round_tasks)
        cursor.execute('DELETE FROM duel_rounds WHERE lesson_id = %s', (lesson_id,))

        round_configs = _get_duel_round_configs(student_count)

        created = []
        for num, name, default_time in round_configs:
            cursor.execute('''
                INSERT INTO duel_rounds (lesson_id, round_number, round_name, time_seconds, status)
                VALUES (%s, %s, %s, %s, 'pending')
                RETURNING id
            ''', (lesson_id, num, name, default_time))
            rid = cursor.fetchone()[0]
            created.append({'id': rid, 'round_number': num, 'round_name': name, 'time_seconds': default_time})

        conn.commit()
        return jsonify({'success': True, 'rounds': created})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/rounds/<int:round_id>/tasks', methods=['POST'])
def set_duel_round_tasks(round_id):
    """Назначить задания к раунду (список task_ids)."""
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    task_ids = data.get('task_ids', [])

    conn = get_db()
    try:
        cursor = conn.cursor()
        # Проверяем владение через lesson
        cursor.execute('''
            SELECT dr.lesson_id FROM duel_rounds dr
            JOIN lessons l ON l.id = dr.lesson_id
            WHERE dr.id = %s AND l.teacher_id = %s AND l.school_id = %s
        ''', (round_id, session['user_id'], g.school_id))
        if not cursor.fetchone():
            return jsonify({'error': 'Not found'}), 404

        # Удаляем старые связи
        cursor.execute('DELETE FROM duel_round_tasks WHERE round_id = %s', (round_id,))

        # Добавляем новые
        for pos, tid in enumerate(task_ids, start=1):
            cursor.execute('''
                INSERT INTO duel_round_tasks (round_id, task_id, position)
                VALUES (%s, %s, %s)
            ''', (round_id, tid, pos))

        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/rounds/<int:round_id>/time', methods=['POST'])
def set_duel_round_time(round_id):
    """Установить время раунда (секунды)."""
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    time_seconds = data.get('time_seconds', 300)

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE duel_rounds dr
            SET time_seconds = %s
            FROM lessons l
            WHERE dr.id = %s AND dr.lesson_id = l.id
              AND l.teacher_id = %s AND l.school_id = %s
        ''', (time_seconds, round_id, session['user_id'], g.school_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/<int:lesson_id>/start', methods=['POST'])
def start_duel(lesson_id):
    """Старт дуэли: создание первой сетки, жеребьёвка, матчи 1-го раунда."""
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Проверяем урок
        cursor.execute('''
            SELECT class_id FROM lessons
            WHERE id = %s AND teacher_id = %s AND school_id = %s AND is_duel = TRUE
        ''', (lesson_id, session['user_id'], g.school_id))
        lesson = cursor.fetchone()
        if not lesson:
            return jsonify({'error': 'Duel lesson not found'}), 404

        class_id = lesson['class_id']

        # Получаем учеников класса, исключая тех, кто исключён из дуэли
        cursor.execute('''
            SELECT id, full_name FROM users
            WHERE class_id = %s AND role = 'student' AND school_id = %s
              AND id NOT IN (
                  SELECT user_id FROM duel_excluded_students WHERE lesson_id = %s
              )
            ORDER BY id
        ''', (class_id, g.school_id, lesson_id))
        students = cursor.fetchall()

        if len(students) < 2:
            return jsonify({'error': 'Недостаточно учеников для дуэли (минимум 2)'}), 400

        # Перемешиваем для случайной жеребьёвки
        random.shuffle(students)

        # Создаём первую сетку (верхняя)
        cursor.execute('''
            INSERT INTO duel_brackets (lesson_id, bracket_number, bracket_name)
            VALUES (%s, 1, 'Верхняя сетка')
            RETURNING id
        ''', (lesson_id,))
        bracket_id = cursor.fetchone()[0]

        # Создаём раунды если их ещё нет
        cursor.execute('SELECT id, round_number FROM duel_rounds WHERE lesson_id = %s ORDER BY round_number', (lesson_id,))
        existing_rounds = cursor.fetchall()
        if not existing_rounds:
            round_configs = _get_duel_round_configs(len(students))
            for num, name, t in round_configs:
                cursor.execute('''
                    INSERT INTO duel_rounds (lesson_id, round_number, round_name, time_seconds, status)
                    VALUES (%s, %s, %s, %s, 'pending')
                    RETURNING id
                ''', (lesson_id, num, name, t))
            cursor.execute('SELECT id, round_number FROM duel_rounds WHERE lesson_id = %s ORDER BY round_number', (lesson_id,))
            existing_rounds = cursor.fetchall()

        rounds_by_num = {r['round_number']: r['id'] for r in existing_rounds}
        round1_id = rounds_by_num.get(1)

        # Создаём пары для 1-го раунда
        match_number = 1
        for i in range(0, len(students), 2):
            p1 = students[i]['id']
            p2 = students[i + 1]['id'] if i + 1 < len(students) else None
            cursor.execute('''
                INSERT INTO duel_matches
                (lesson_id, round_id, bracket_id, match_number, player1_id, player2_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'active')
            ''', (lesson_id, round1_id, bracket_id, match_number, p1, p2))
            match_number += 1

        # Активируем 1-й раунд
        cursor.execute('''
            UPDATE duel_rounds SET status = 'active', started_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (round1_id,))

        conn.commit()
        return jsonify({'success': True, 'bracket_id': bracket_id, 'matches_created': match_number - 1})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/<int:lesson_id>/my_match', methods=['GET'])
def get_my_duel_match(lesson_id):
    """Получить текущий или последний завершённый матч ученика в дуэли."""
    if 'user_id' not in session or session['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Находим активный раунд
        cursor.execute('''
            SELECT id, round_number, round_name, time_seconds, status
            FROM duel_rounds
            WHERE lesson_id = %s AND status IN ('active', 'overtime')
            ORDER BY round_number
            LIMIT 1
        ''', (lesson_id,))
        current_round = cursor.fetchone()

        # Если нет активного — берём последний завершённый
        if not current_round:
            cursor.execute('''
                SELECT id, round_number, round_name, time_seconds, status
                FROM duel_rounds
                WHERE lesson_id = %s AND status = 'completed'
                ORDER BY round_number DESC
                LIMIT 1
            ''', (lesson_id,))
            current_round = cursor.fetchone()

        if not current_round:
            return jsonify({'error': 'Нет активного или завершённого раунда'}), 404

        # Находим матч ученика в этом раунде
        cursor.execute('''
            SELECT dm.*,
                   p1.full_name AS player1_name,
                   p2.full_name AS player2_name
            FROM duel_matches dm
            LEFT JOIN users p1 ON p1.id = dm.player1_id
            LEFT JOIN users p2 ON p2.id = dm.player2_id
            WHERE dm.round_id = %s
              AND (dm.player1_id = %s OR dm.player2_id = %s)
        ''', (current_round['id'], user_id, user_id))
        match = cursor.fetchone()
        if not match:
            return jsonify({'error': 'Матч не найден'}), 404

            # Задания раунда — генерируем варианты для ученика
        cursor.execute('''
            SELECT lt.id, lt.question, lt.answer, lt.template_id, lt.photo_path
            FROM duel_round_tasks drt
            JOIN lesson_tasks lt ON lt.id = drt.task_id
            WHERE drt.round_id = %s
            ORDER BY drt.position
        ''', (current_round['id'],))
        base_tasks = cursor.fetchall()

        tasks = []
        for task in base_tasks:
            # Проверяем сохранённый вариант
            cursor.execute('''
                SELECT variant_data FROM student_task_variants
                WHERE lesson_id = %s AND user_id = %s AND task_id = %s AND school_id = %s
            ''', (lesson_id, user_id, task['id'], g.school_id))
            variant_row = cursor.fetchone()

            if variant_row:
                raw = variant_row['variant_data']
                if isinstance(raw, str):
                    variant_data = json.loads(raw)
                else:
                    variant_data = raw or {}
                question = variant_data.get('generated_question', task['question'])
                computed_answer = variant_data.get('computed_answer', '')
                photo_path = task.get('photo_path', '') or variant_data.get('photo_path', '') or ''
                answer_type = 'numeric'
                if task['template_id']:
                    cursor.execute('SELECT answer_type FROM task_templates WHERE id = %s', (task['template_id'],))
                    r = cursor.fetchone()
                    answer_type = r['answer_type'] if r else 'numeric'
            else:
                # Генерируем новый вариант
                if task['template_id']:
                    cursor.execute('SELECT * FROM task_templates WHERE id = %s', (task['template_id'],))
                    template = cursor.fetchone()
                    template_dict = dict(template)
                    params = template_dict['parameters']
                    if isinstance(params, str):
                        params = json.loads(params)
                    template_dict['parameters'] = params

                    student_mark = infer_student_mark(user_id)
                    if template_dict.get('photo_path'):
                        variant = TaskGenerator.generate_task_variant(template_dict, band=student_mark)
                        question = ''
                        computed_answer = variant['correct_answer']
                        answer_type = template_dict.get('answer_type', 'numeric')
                    else:
                        variant = TaskGenerator.generate_task_variant(template_dict, band=student_mark)
                        question = variant['question']
                        computed_answer = variant['correct_answer']
                        answer_type = template_dict.get('answer_type', 'numeric')
                else:
                    question = task['question']
                    computed_answer = task['answer']
                    answer_type = 'numeric'

                photo_path = task.get('photo_path', '') or ''

                cursor.execute('''
                    INSERT INTO student_task_variants (lesson_id, user_id, task_id, variant_data, school_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (lesson_id, user_id, task_id)
                    DO UPDATE SET variant_data = EXCLUDED.variant_data, created_at = CURRENT_TIMESTAMP
                ''', (
                    lesson_id, user_id, task['id'],
                    json.dumps({
                        'params': variant.get('params', {}) if task['template_id'] else {},
                        'generated_question': question,
                        'computed_answer': computed_answer,
                        'photo_path': photo_path,
                        'initial_choice_idx': variant.get('choice_idx') if task['template_id'] else None,
                        'current_choice_idx': variant.get('choice_idx') if task['template_id'] else None,
                        'is_retry': False,
                        'retry_generated_question': None,
                        'retry_computed_answer': None,
                        'retry_params': None,
                        'retry_choice_idx': None
                    }),
                    g.school_id
                ))

            tasks.append({
                'id': task['id'],
                'question': question,
                'answer': computed_answer,
                'answer_type': answer_type,
                'photo_path': photo_path,
                'template_id': task['template_id']
            })

        # Ищем следующий матч ученика (для показа следующего соперника)
        next_match = None
        cursor.execute('''
            SELECT dr.id FROM duel_rounds dr
            WHERE dr.lesson_id = %s AND dr.round_number = %s
        ''', (lesson_id, current_round['round_number'] + 1))
        next_round_row = cursor.fetchone()
        if next_round_row:
            cursor.execute('''
                SELECT dm.*,
                       p1.full_name AS player1_name,
                       p2.full_name AS player2_name
                FROM duel_matches dm
                LEFT JOIN users p1 ON p1.id = dm.player1_id
                LEFT JOIN users p2 ON p2.id = dm.player2_id
                WHERE dm.round_id = %s
                  AND (dm.player1_id = %s OR dm.player2_id = %s)
            ''', (next_round_row['id'], user_id, user_id))
            next_match = cursor.fetchone()

        conn.commit()

        return jsonify(_json_safe({
            'match': dict(match),
            'round': dict(current_round),
            'tasks': tasks,
            'next_match': dict(next_match) if next_match else None,
            'overtime_active': bool(match.get('overtime_active')),
            'overtime_ends_at': match['overtime_ended_at'].isoformat() if match.get('overtime_ended_at') else None
        }))
    except Exception as e:
        conn.rollback()
        print(f"Error in get_my_duel_match: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/match/<int:match_id>/answer', methods=['POST'])
def submit_duel_answer(match_id):
    """Ученик отправляет ответ в матче."""
    if 'user_id' not in session or session['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    data = request.get_json()
    task_id = data.get('task_id')
    answer = data.get('answer', '')
    is_correct = data.get('is_correct', False)
    ai_solution = data.get('ai_solution', '')
    is_overtime = data.get('is_overtime', False)
    print(f"[DUEL ANSWER] match_id={match_id} user_id={user_id} task_id={task_id} is_correct={is_correct} is_overtime={is_overtime}")

    conn = get_db()
    try:
        cursor = conn.cursor()

        # Проверяем, что матч активен и ученик в нём участвует
        cursor.execute('''
            SELECT status, player1_id, player2_id, round_id, overtime_active FROM duel_matches
            WHERE id = %s AND (player1_id = %s OR player2_id = %s)
        ''', (match_id, user_id, user_id))
        row = cursor.fetchone()
        if not row:
            print(f"[DUEL ANSWER] Match not found: match_id={match_id} user_id={user_id}")
            return jsonify({'error': 'Match not found'}), 404
        if row[0] != 'active':
            print(f"[DUEL ANSWER] Match not active: match_id={match_id} status={row[0]}")
            return jsonify({'error': 'Матч не активен'}), 400

        # Автоопределяем overtime по флагу матча, если клиент не прислал
        if not is_overtime and row[4]:
            is_overtime = True

        # Сохраняем ответ
        cursor.execute('''
            INSERT INTO duel_match_answers (match_id, user_id, task_id, answer, is_correct, ai_solution, is_overtime)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        ''', (match_id, user_id, task_id, answer, is_correct, ai_solution, is_overtime))
        print(f"[DUEL ANSWER] Saved answer for match_id={match_id} user_id={user_id} task_id={task_id}")

        # Обновляем счёт матча, время первого и последнего правильного ответа
        if is_correct:
            if user_id == row[1]:  # player1
                cursor.execute('''
                    UPDATE duel_matches
                    SET player1_score = player1_score + 1,
                        player1_first_correct_at = COALESCE(player1_first_correct_at, CURRENT_TIMESTAMP),
                        player1_last_correct_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                ''', (match_id,))
                print(f"[DUEL ANSWER] Updated p1_score for match_id={match_id}")
            elif user_id == row[2]:  # player2
                cursor.execute('''
                    UPDATE duel_matches
                    SET player2_score = player2_score + 1,
                        player2_first_correct_at = COALESCE(player2_first_correct_at, CURRENT_TIMESTAMP),
                        player2_last_correct_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                ''', (match_id,))
                print(f"[DUEL ANSWER] Updated p2_score for match_id={match_id}")

        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/match/<int:match_id>/my_answers', methods=['GET'])
def get_duel_my_answers(match_id):
    """Получить все ответы ученика в матче (для показа после раунда)."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = session['user_id']

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('''
            SELECT dma.task_id, dma.answer, dma.is_correct, dma.ai_solution,
                   lt.question, lt.answer AS correct_answer
            FROM duel_match_answers dma
            JOIN lesson_tasks lt ON lt.id = dma.task_id
            WHERE dma.match_id = %s AND dma.user_id = %s
            ORDER BY dma.answered_at
        ''', (match_id, user_id))
        rows = cursor.fetchall()
        answers = []
        for r in rows:
            answers.append({
                'task_id': r['task_id'],
                'answer': r['answer'],
                'is_correct': r['is_correct'],
                'ai_solution': r['ai_solution'],
                'question': r['question'],
                'correct_answer': r['correct_answer']
            })
        return jsonify({'answers': answers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/match/<int:match_id>/complete', methods=['POST'])
def complete_duel_match(match_id):
    """Завершить матч (по таймауту или когда оба ответили). Определить победителя."""
    if 'user_id' not in session or session['role'] not in ('teacher', 'student'):
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute('''
            SELECT * FROM duel_matches WHERE id = %s
        ''', (match_id,))
        match = cursor.fetchone()
        if not match:
            return jsonify({'error': 'Match not found'}), 404
        if match['status'] == 'completed':
            return jsonify({'success': True, 'winner_id': match['winner_id']})

        p1_score = match['player1_score'] or 0
        p2_score = match['player2_score'] or 0
        p1_first = match['player1_first_correct_at']
        p2_first = match['player2_first_correct_at']
        p1_id = match['player1_id']
        p2_id = match['player2_id']

        winner_id = None
        loser_id = None
        tie_reason = ''

        if p1_score > p2_score:
            winner_id = p1_id
            loser_id = p2_id
            tie_reason = 'score'
        elif p2_score > p1_score:
            winner_id = p2_id
            loser_id = p1_id
            tie_reason = 'score'
        else:
            # Ничья — побеждает тот, кто первым дал правильный ответ
            if p1_first and p2_first:
                if p1_first < p2_first:
                    winner_id = p1_id
                    loser_id = p2_id
                    tie_reason = 'first_correct'
                elif p2_first < p1_first:
                    winner_id = p2_id
                    loser_id = p1_id
                    tie_reason = 'first_correct'
                else:
                    # Одинаковое время — случайный выбор
                    import random
                    winner_id = random.choice([p1_id, p2_id])
                    loser_id = p2_id if winner_id == p1_id else p1_id
                    tie_reason = 'random'
            elif p1_first:
                winner_id = p1_id
                loser_id = p2_id
                tie_reason = 'first_correct'
            elif p2_first:
                winner_id = p2_id
                loser_id = p1_id
                tie_reason = 'first_correct'
            else:
                # Никто не ответил — случайный победитель
                import random
                winner_id = random.choice([p1_id, p2_id])
                loser_id = p2_id if winner_id == p1_id else p1_id
                tie_reason = 'random'

        cursor.execute('''
            UPDATE duel_matches
            SET winner_id = %s, loser_id = %s, status = 'completed', ended_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (winner_id, loser_id, match_id))

        conn.commit()
        return jsonify({'success': True, 'winner_id': winner_id, 'loser_id': loser_id,
                        'player1_score': p1_score, 'player2_score': p2_score})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/<int:lesson_id>/next-round', methods=['POST'])
def advance_duel_round(lesson_id):
    """Переход к следующему раунду. Требует, чтобы текущий раунд был остановлен."""
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Текущий раунд (active, overtime или completed)
        cursor.execute('''
            SELECT id, round_number, status FROM duel_rounds
            WHERE lesson_id = %s AND status IN ('active', 'overtime', 'completed')
            ORDER BY round_number DESC LIMIT 1
        ''', (lesson_id,))
        current_round = cursor.fetchone()
        if not current_round:
            return jsonify({'error': 'Нет активного раунда'}), 400

        current_round_id = current_round['id']
        current_round_num = current_round['round_number']

        # Если текущий раунд ещё не остановлен — сообщаем
        if current_round['status'] in ('active', 'overtime'):
            return jsonify({'error': 'Сначала остановите текущий раунд'}), 400

        # Определяем, является ли текущий раунд финалом (последним)
        cursor.execute('''
            SELECT MAX(round_number) as max_round FROM duel_rounds WHERE lesson_id = %s
        ''', (lesson_id,))
        max_round_row = cursor.fetchone()
        max_round = max_round_row['max_round'] or current_round_num

        # Если это был финал — формируем leaderboard
        if current_round_num >= max_round:
            _finalize_duel_leaderboard(conn, cursor, lesson_id)
            conn.commit()
            return jsonify({'success': True, 'finished': True})

        # Следующий раунд
        next_round_num = current_round_num + 1
        cursor.execute('''
            SELECT id FROM duel_rounds
            WHERE lesson_id = %s AND round_number = %s
        ''', (lesson_id, next_round_num))
        next_round = cursor.fetchone()
        if not next_round:
            return jsonify({'error': 'Следующий раунд не найден'}), 400
        next_round_id = next_round['id']

        # Получаем все сетки урока
        cursor.execute('''
            SELECT id, bracket_number, bracket_name FROM duel_brackets
            WHERE lesson_id = %s ORDER BY bracket_number
        ''', (lesson_id,))
        brackets = {b['bracket_number']: dict(b) for b in cursor.fetchall()}

        # Собираем победителей и проигравших по сеткам
        participants_by_bracket = {}  # bnum -> [user_ids]

        for bnum, bracket in sorted(brackets.items()):
            cursor.execute('''
                SELECT match_number, winner_id, loser_id
                FROM duel_matches
                WHERE round_id = %s AND bracket_id = %s AND status = 'completed'
                ORDER BY match_number
            ''', (current_round_id, bracket['id']))
            matches = cursor.fetchall()
            if not matches:
                continue

            winners = [m['winner_id'] for m in matches if m['winner_id']]
            losers = [m['loser_id'] for m in matches if m['loser_id']]

            # Победители остаются в той же сетке
            if bnum not in participants_by_bracket:
                participants_by_bracket[bnum] = []
            participants_by_bracket[bnum].extend(winners)

            # Проигравшие падают в сетку +1
            lower_bnum = bnum + 1
            if lower_bnum not in participants_by_bracket:
                participants_by_bracket[lower_bnum] = []
            participants_by_bracket[lower_bnum].extend(losers)

        # Создаём матчи для каждой сетки
        match_num = 1
        for bnum in sorted(participants_by_bracket.keys()):
            participants = participants_by_bracket[bnum]
            if not participants:
                continue

            # Создаём/получаем брэкет
            if bnum not in brackets:
                cursor.execute('''
                    INSERT INTO duel_brackets (lesson_id, bracket_number, bracket_name)
                    VALUES (%s, %s, %s)
                    RETURNING id
                ''', (lesson_id, bnum, f'Сетка {bnum}'))
                bracket_id = cursor.fetchone()['id']
                brackets[bnum] = {'id': bracket_id, 'bracket_number': bnum}
            else:
                bracket_id = brackets[bnum]['id']

            # Формируем пары: (1+2), (3+4), ...
            for i in range(0, len(participants), 2):
                if i + 1 < len(participants):
                    cursor.execute('''
                        INSERT INTO duel_matches
                        (lesson_id, round_id, bracket_id, match_number, player1_id, player2_id, status)
                        VALUES (%s, %s, %s, %s, %s, %s, 'active')
                    ''', (lesson_id, next_round_id, bracket_id, match_num, participants[i], participants[i + 1]))
                    match_num += 1
                else:
                    # Бай — автоматически проходит дальше (completed матч)
                    cursor.execute('''
                        INSERT INTO duel_matches
                        (lesson_id, round_id, bracket_id, match_number, player1_id, player2_id, winner_id, loser_id, status)
                        VALUES (%s, %s, %s, %s, %s, NULL, %s, NULL, 'completed')
                    ''', (lesson_id, next_round_id, bracket_id, match_num, participants[i], participants[i]))
                    match_num += 1

        # Активируем следующий раунд
        cursor.execute('''
            UPDATE duel_rounds SET status = 'active', started_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (next_round_id,))

        conn.commit()
        return jsonify({'success': True, 'next_round': next_round_num})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


def _get_duel_round_configs(student_count):
    """Возвращает список (round_number, round_name, time_seconds) в зависимости от числа участников."""
    if student_count < 2:
        return []
    num_rounds = max(1, math.ceil(math.log2(student_count)))
    configs = []
    for i in range(1, num_rounds + 1):
        if i == num_rounds:
            name = 'Финал'
        elif i == num_rounds - 1:
            name = '1/2'
        elif i == num_rounds - 2:
            name = '1/4'
        elif i == num_rounds - 3:
            name = '1/8'
        elif i == num_rounds - 4:
            name = '1/16'
        elif i == num_rounds - 5:
            name = '1/32'
        elif i == num_rounds - 6:
            name = '1/64'
        else:
            name = f'Раунд {i}'
        configs.append((i, name, 300))
    return configs


def _finalize_duel_leaderboard(conn, cursor, lesson_id):
    """Формирует итоговую таблицу лидеров после финала."""
    # Определяем номера финального и полуфинального раундов
    cursor.execute('''
        SELECT MAX(round_number) as max_round FROM duel_rounds WHERE lesson_id = %s
    ''', (lesson_id,))
    max_round = cursor.fetchone()['max_round'] or 1
    semi_round = max_round - 1 if max_round > 1 else 1

    # Получаем финальный матч
    cursor.execute('''
        SELECT winner_id, loser_id, player1_score, player2_score
        FROM duel_matches dm
        JOIN duel_rounds dr ON dr.id = dm.round_id
        WHERE dr.lesson_id = %s AND dr.round_number = %s
        LIMIT 1
    ''', (lesson_id, max_round))
    final = cursor.fetchone()

    # Собираем статистику по всем матчам
    cursor.execute('''
        SELECT winner_id, loser_id FROM duel_matches dm
        JOIN duel_rounds dr ON dr.id = dm.round_id
        WHERE dr.lesson_id = %s AND dm.status = 'completed'
    ''', (lesson_id,))
    all_matches = cursor.fetchall()

    stats = {}
    for m in all_matches:
        for uid, key in [(m['winner_id'], 'wins'), (m['loser_id'], 'losses')]:
            if uid:
                if uid not in stats:
                    stats[uid] = {'wins': 0, 'losses': 0, 'total_score': 0}
                stats[uid][key] += 1

    # Определяем места
    places = []
    if final:
        places.append((1, final['winner_id']))
        places.append((2, final['loser_id']))
        # 3 место — лучший из проигравших в полуфинале (предпоследний раунд)
        if semi_round >= 1:
            cursor.execute('''
                SELECT loser_id FROM duel_matches dm
                JOIN duel_rounds dr ON dr.id = dm.round_id
                WHERE dr.lesson_id = %s AND dr.round_number = %s AND dm.status = 'completed'
                ORDER BY dm.player1_score + dm.player2_score DESC
                LIMIT 1
            ''', (lesson_id, semi_round))
            third = cursor.fetchone()
            if third and third['loser_id']:
                places.append((3, third['loser_id']))

    # Остальные — по количеству побед
    placed_uids = {uid for _, uid in places}
    remaining = [(uid, s['wins']) for uid, s in stats.items() if uid not in placed_uids]
    remaining.sort(key=lambda x: -x[1])
    place = 4
    for uid, _ in remaining:
        places.append((place, uid))
        place += 1

    # Сохраняем
    cursor.execute('DELETE FROM duel_leaderboard WHERE lesson_id = %s', (lesson_id,))
    for place, uid in places:
        s = stats.get(uid, {'wins': 0, 'losses': 0, 'total_score': 0})
        cursor.execute('''
            INSERT INTO duel_leaderboard (lesson_id, user_id, final_place, wins, losses, total_score)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (lesson_id, uid, place, s['wins'], s['losses'], s['total_score']))

    # Отмечаем урок как ended
    cursor.execute('UPDATE lessons SET ended = TRUE WHERE id = %s', (lesson_id,))


def _resolve_match_winner(p1_id, p2_id, p1_score, p2_score, p1_first, p2_first, p1_last, p2_last):
    """Определить победителя матча. Возвращает (winner_id, loser_id, tie_reason).
    Иерархия: score -> first_correct -> last_correct -> random."""
    p1_score = p1_score or 0
    p2_score = p2_score or 0

    if p1_score > p2_score:
        return p1_id, p2_id, 'score'
    elif p2_score > p1_score:
        return p2_id, p1_id, 'score'
    else:
        # Ничья — сначала по first_correct (кто раньше начал)
        if p1_first and p2_first:
            if p1_first < p2_first:
                return p1_id, p2_id, 'first_correct'
            elif p2_first < p1_first:
                return p2_id, p1_id, 'first_correct'
            # одинаковое first_correct — переходим к last_correct
        elif p1_first:
            return p1_id, p2_id, 'first_correct'
        elif p2_first:
            return p2_id, p1_id, 'first_correct'

        # last_correct (кто раньше закончил)
        if p1_last and p2_last:
            if p1_last < p2_last:
                return p1_id, p2_id, 'last_correct'
            elif p2_last < p1_last:
                return p2_id, p1_id, 'last_correct'
        elif p1_last:
            return p1_id, p2_id, 'last_correct'
        elif p2_last:
            return p2_id, p1_id, 'last_correct'

        import random
        winner = random.choice([p1_id, p2_id])
        return winner, (p2_id if winner == p1_id else p1_id), 'random'


def _complete_all_matches_in_round(conn, cursor, round_id):
    """Завершить все незавершённые матчи в раунде. Учитывает overtime очки."""
    cursor.execute('''
        SELECT id, player1_id, player2_id, player1_score, player2_score,
               player1_first_correct_at, player2_first_correct_at,
               player1_last_correct_at, player2_last_correct_at, status,
               overtime_active
        FROM duel_matches
        WHERE round_id = %s AND status != 'completed'
    ''', (round_id,))
    for m in cursor.fetchall():
        p1_score = m['player1_score'] or 0
        p2_score = m['player2_score'] or 0

        w, l, reason = _resolve_match_winner(
            m['player1_id'], m['player2_id'],
            p1_score, p2_score,
            m['player1_first_correct_at'], m['player2_first_correct_at'],
            m['player1_last_correct_at'], m['player2_last_correct_at']
        )
        cursor.execute('''
            UPDATE duel_matches
            SET winner_id = %s, loser_id = %s, status = 'completed', ended_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (w, l, m['id']))


@app.route('/api/duel/<int:lesson_id>/stop-round', methods=['POST'])
def stop_duel_round(lesson_id):
    """Остановить текущий раунд досрочно. Завершает все матчи и показывает результаты ученикам."""
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute('''
            SELECT id, round_number FROM duel_rounds
            WHERE lesson_id = %s AND status IN ('active', 'overtime')
            ORDER BY round_number DESC LIMIT 1
        ''', (lesson_id,))
        current_round = cursor.fetchone()
        if not current_round:
            return jsonify({'error': 'Нет активного раунда'}), 400

        _complete_all_matches_in_round(conn, cursor, current_round['id'])

        cursor.execute('''
            UPDATE duel_rounds SET status = 'completed', ended_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (current_round['id'],))

        # Проверяем, можно ли запустить overtime (есть следующий раунд и не было overtime)
        cursor.execute('''
            SELECT COUNT(*) as cnt
            FROM duel_matches
            WHERE round_id = %s AND overtime_active = TRUE
        ''', (current_round['id'],))
        had_overtime = cursor.fetchone()['cnt'] > 0

        cursor.execute('''
            SELECT COUNT(*) as cnt
            FROM duel_rounds
            WHERE lesson_id = %s AND round_number > %s
        ''', (lesson_id, current_round['round_number']))
        has_next_round = cursor.fetchone()['cnt'] > 0
        needs_overtime = has_next_round and not had_overtime

        conn.commit()
        return jsonify({'success': True, 'round_number': current_round['round_number'], 'needs_overtime': needs_overtime})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/<int:lesson_id>/start-overtime', methods=['POST'])
def start_overtime(lesson_id):
    """Запустить дополнительное время для матчей 0-0 в текущем раунде."""
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    time_seconds = int(data.get('time_seconds', 300))
    if time_seconds < 10:
        return jsonify({'error': 'Минимум 10 секунд'}), 400

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute('''
            SELECT id FROM duel_rounds
            WHERE lesson_id = %s AND status = 'completed'
            ORDER BY round_number DESC LIMIT 1
        ''', (lesson_id,))
        current_round = cursor.fetchone()
        if not current_round:
            return jsonify({'error': 'Нет завершенного раунда'}), 400

        # Сбрасываем ВСЕ матчи раунда для overtime (сохраняем текущие очки)
        cursor.execute('''
            UPDATE duel_matches
            SET status = 'active',
                winner_id = NULL,
                loser_id = NULL,
                overtime_active = TRUE,
                overtime_started_at = CURRENT_TIMESTAMP,
                overtime_ended_at = CURRENT_TIMESTAMP + INTERVAL '%s seconds'
            WHERE round_id = %s
        ''', (time_seconds, current_round['id']))

        # Переводим раунд в статус overtime, чтобы ученики видели активный раунд
        cursor.execute('''
            UPDATE duel_rounds
            SET status = 'overtime',
                time_seconds = %s,
                started_at = CURRENT_TIMESTAMP,
                ended_at = CURRENT_TIMESTAMP + INTERVAL '%s seconds'
            WHERE id = %s
        ''', (time_seconds, time_seconds, current_round['id']))

        # ==== Генерация новых вариантов задач для ВСЕХ учеников ====
        cursor.execute('''
            SELECT lt.id, lt.question, lt.answer, lt.template_id, lt.photo_path
            FROM lesson_tasks lt
            JOIN duel_round_tasks drt ON drt.task_id = lt.id
            WHERE drt.round_id = %s
            ORDER BY drt.position
        ''', (current_round['id'],))
        round_tasks = cursor.fetchall()

        # Кэшируем шаблоны
        template_cache = {}
        for t in round_tasks:
            if t['template_id'] and t['template_id'] not in template_cache:
                cursor.execute('SELECT * FROM task_templates WHERE id = %s', (t['template_id'],))
                tmpl = cursor.fetchone()
                if tmpl:
                    td = dict(tmpl)
                    p = td.get('parameters', '{}')
                    if isinstance(p, str):
                        try:
                            p = json.loads(p)
                        except Exception:
                            p = {}
                    td['parameters'] = p
                    template_cache[t['template_id']] = td

        cursor.execute('''
            SELECT id, player1_id, player2_id FROM duel_matches
            WHERE round_id = %s
        ''', (current_round['id'],))
        round_matches = cursor.fetchall()

        print(f"[OVERTIME] Generating ALL new variants for round={current_round['id']} tasks={len(round_tasks)} matches={len(round_matches)}")
        for m in round_matches:
            for player_id in (m['player1_id'], m['player2_id']):
                if not player_id:
                    continue
                try:
                    student_mark = infer_student_mark(player_id)
                    for t in round_tasks:
                        # Генерируем НОВЫЙ вариант для ВСЕХ задач (независимо от предыдущих ответов)
                        variant = None
                        if t['template_id'] and t['template_id'] in template_cache:
                            td = template_cache[t['template_id']]
                            variant = TaskGenerator.generate_task_variant(td, band=student_mark)
                            if variant:
                                if td.get('photo_path'):
                                    question = ''
                                    computed_answer = variant['correct_answer']
                                    answer_type = td.get('answer_type', 'numeric')
                                else:
                                    question = variant['question']
                                    computed_answer = variant['correct_answer']
                                    answer_type = td.get('answer_type', 'numeric')
                            else:
                                question = t['question']
                                computed_answer = t['answer']
                                answer_type = 'numeric'
                        else:
                            question = t['question']
                            computed_answer = t['answer']
                            answer_type = 'numeric'

                        photo_path = t.get('photo_path', '') or ''

                        variant_json = json.dumps({
                            'params': variant.get('params', {}) if variant else {},
                            'generated_question': question,
                            'computed_answer': computed_answer,
                            'photo_path': photo_path,
                            'initial_choice_idx': variant.get('choice_idx') if variant else None,
                            'current_choice_idx': variant.get('choice_idx') if variant else None,
                            'is_retry': False,
                            'retry_generated_question': None,
                            'retry_computed_answer': None,
                            'retry_params': None,
                            'retry_choice_idx': None
                        })
                        cursor.execute('''
                            INSERT INTO student_task_variants (lesson_id, user_id, task_id, variant_data, school_id)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (lesson_id, user_id, task_id)
                            DO UPDATE SET variant_data = EXCLUDED.variant_data,
                                          school_id = EXCLUDED.school_id,
                                          created_at = CURRENT_TIMESTAMP
                        ''', (
                            lesson_id, player_id, t['id'],
                            variant_json,
                            g.school_id
                        ))
                        print(f"[OVERTIME] task={t['id']} player={player_id} q={question[:70]} ans={computed_answer}")
                except Exception as e:
                    print(f"[OVERTIME] Error generating variant for match={m['id']} player={player_id}: {e}")
                    import traceback
                    traceback.print_exc()

        conn.commit()
        return jsonify({'success': True, 'time_seconds': time_seconds})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/<int:lesson_id>/leaderboard', methods=['GET'])
def get_duel_leaderboard(lesson_id):
    """Получить таблицу лидеров дуэли (динамически, даже если финал ещё не состоялся)."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Проверяем, есть ли уже финальная таблица
        cursor.execute('''
            SELECT dl.*, u.full_name
            FROM duel_leaderboard dl
            JOIN users u ON u.id = dl.user_id
            WHERE dl.lesson_id = %s
            ORDER BY dl.final_place
        ''', (lesson_id,))
        rows = cursor.fetchall()
        if rows:
            return jsonify({'leaderboard': _json_safe([dict(r) for r in rows])})

        # Динамический расчёт из матчей
        cursor.execute('''
            SELECT dm.player1_id, dm.player2_id, dm.winner_id, dm.loser_id,
                   dm.player1_score, dm.player2_score,
                   u1.full_name as p1_name, u2.full_name as p2_name
            FROM duel_matches dm
            JOIN duel_rounds dr ON dr.id = dm.round_id
            LEFT JOIN users u1 ON u1.id = dm.player1_id
            LEFT JOIN users u2 ON u2.id = dm.player2_id
            WHERE dr.lesson_id = %s AND dm.status = 'completed'
        ''', (lesson_id,))
        matches = cursor.fetchall()

        stats = {}
        for m in matches:
            p1 = m['player1_id']
            p2 = m['player2_id']
            if p1:
                if p1 not in stats:
                    stats[p1] = {'wins': 0, 'losses': 0, 'total_score': 0, 'tasks_solved': 0, 'full_name': m['p1_name'] or '—'}
                stats[p1]['total_score'] += m['player1_score'] or 0
                if m['winner_id'] == p1:
                    stats[p1]['wins'] += 1
                elif m['loser_id'] == p1:
                    stats[p1]['losses'] += 1
            if p2:
                if p2 not in stats:
                    stats[p2] = {'wins': 0, 'losses': 0, 'total_score': 0, 'tasks_solved': 0, 'full_name': m['p2_name'] or '—'}
                stats[p2]['total_score'] += m['player2_score'] or 0
                if m['winner_id'] == p2:
                    stats[p2]['wins'] += 1
                elif m['loser_id'] == p2:
                    stats[p2]['losses'] += 1

        # Считаем tasks_solved из duel_match_answers
        cursor.execute('''
            SELECT dma.user_id, COUNT(*) as solved
            FROM duel_match_answers dma
            JOIN duel_matches dm ON dm.id = dma.match_id
            JOIN duel_rounds dr ON dr.id = dm.round_id
            WHERE dr.lesson_id = %s AND dma.is_correct = TRUE
            GROUP BY dma.user_id
        ''', (lesson_id,))
        for row in cursor.fetchall():
            uid = row['user_id']
            if uid in stats:
                stats[uid]['tasks_solved'] = row['solved']

        # Формируем leaderboard с сортировкой: победы > total_score > tasks_solved
        leaderboard = []
        for uid, s in stats.items():
            leaderboard.append({
                'user_id': uid,
                'full_name': s['full_name'],
                'wins': s['wins'],
                'losses': s['losses'],
                'total_score': s['total_score'],
                'tasks_solved': s['tasks_solved'],
                'matches_played': s['wins'] + s['losses']
            })
        leaderboard.sort(key=lambda x: (-x['wins'], -x['total_score'], -x['tasks_solved']))

        # Добавляем place
        for i, row in enumerate(leaderboard, start=1):
            row['final_place'] = i

        return jsonify({'leaderboard': _json_safe(leaderboard)})
    finally:
        conn.close()


@app.route('/api/duel/<int:lesson_id>/excluded_students', methods=['GET'])
def get_excluded_students(lesson_id):
    """Получить список учеников, исключённых из дуэли."""
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('''
            SELECT des.user_id, u.full_name
            FROM duel_excluded_students des
            JOIN users u ON u.id = des.user_id
            WHERE des.lesson_id = %s
            ORDER BY u.full_name
        ''', (lesson_id,))
        rows = cursor.fetchall()
        return jsonify({'excluded': [{'user_id': r['user_id'], 'full_name': r['full_name']} for r in rows]})
    finally:
        conn.close()


@app.route('/api/duel/<int:lesson_id>/exclude/<int:student_id>', methods=['POST'])
def exclude_student_from_duel(lesson_id, student_id):
    """Исключить ученика из дуэли."""
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO duel_excluded_students (lesson_id, user_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        ''', (lesson_id, student_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/<int:lesson_id>/include/<int:student_id>', methods=['POST'])
def include_student_in_duel(lesson_id, student_id):
    """Вернуть ученика в дуэль."""
    if 'user_id' not in session or session['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM duel_excluded_students
            WHERE lesson_id = %s AND user_id = %s
        ''', (lesson_id, student_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/api/duel/<int:lesson_id>/bracket', methods=['GET'])
def get_duel_bracket(lesson_id):
    """Получить полную структуру турнирной сетки с детальной статистикой."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Все раунды
        cursor.execute('''
            SELECT id, round_number, round_name, status, time_seconds
            FROM duel_rounds WHERE lesson_id = %s ORDER BY round_number
        ''', (lesson_id,))
        rounds = [dict(r) for r in cursor.fetchall()]

        # Все матчи с именами
        cursor.execute('''
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
        ''', (lesson_id,))
        matches = [dict(m) for m in cursor.fetchall()]

        # Статистика ответов по каждому матчу
        match_ids = [m['id'] for m in matches]
        answer_stats = {}
        if match_ids:
            cursor.execute('''
                SELECT match_id, user_id,
                       COUNT(*) FILTER (WHERE is_correct = TRUE) AS correct_count,
                       COUNT(*) AS total_answers
                FROM duel_match_answers
                WHERE match_id = ANY(%s)
                GROUP BY match_id, user_id
            ''', (match_ids,))
            for row in cursor.fetchall():
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

        return jsonify(_json_safe({'rounds': rounds, 'matches': matches}))
    finally:
        conn.close()


@app.route('/api/duel/<int:lesson_id>/status', methods=['GET'])
def get_duel_status(lesson_id):
    """Получить статус дуэли (активный раунд, завершена ли)."""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('''
            SELECT ended, is_duel FROM lessons WHERE id = %s
        ''', (lesson_id,))
        lesson = cursor.fetchone()

        cursor.execute('''
            SELECT * FROM duel_rounds
            WHERE lesson_id = %s ORDER BY round_number
        ''', (lesson_id,))
        rounds = [dict(r) for r in cursor.fetchall()]

        active_round = next((r for r in rounds if r['status'] in ('active', 'overtime')), None)
        completed_rounds = [r for r in rounds if r['status'] == 'completed']
        last_completed = max(completed_rounds, key=lambda r: r['round_number']) if completed_rounds else None

        # Overtime доступен для завершённого раунда, если есть следующий и не было overtime
        needs_overtime = False
        if last_completed and not active_round:
            cursor.execute('''
                SELECT COUNT(*) as cnt
                FROM duel_matches
                WHERE round_id = %s AND overtime_active = TRUE
            ''', (last_completed['id'],))
            had_overtime = cursor.fetchone()['cnt'] > 0

            cursor.execute('''
                SELECT COUNT(*) as cnt
                FROM duel_rounds
                WHERE lesson_id = %s AND round_number > %s
            ''', (lesson_id, last_completed['round_number']))
            needs_overtime = cursor.fetchone()['cnt'] > 0 and not had_overtime

        return jsonify(_json_safe({
            'is_duel': bool(lesson['is_duel']) if lesson else False,
            'ended': bool(lesson['ended']) if lesson else False,
            'active_round': dict(active_round) if active_round else None,
            'last_completed_round': dict(last_completed) if last_completed else None,
            'needs_overtime': needs_overtime,
            'rounds': rounds
        }))
    finally:
        conn.close()


# =============================================================================

if __name__ == '__main__':
    cleanup_guest_students()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)