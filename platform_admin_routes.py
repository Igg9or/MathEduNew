from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash
import psycopg2
import psycopg2.extras

platform_admin_bp = Blueprint("platform_admin", __name__)

def require_platform_admin():
    return ("user_id" in session) and (session.get("role") == "platform_admin")

@platform_admin_bp.route("/schools", methods=["GET", "POST"])
def schools_page():
    if not require_platform_admin():
        return redirect(url_for("login"))

    from app import get_db  # берём твою функцию get_db

    # создать школу
    if request.method == "POST" and request.form.get("action") == "create_school":
        name = (request.form.get("name") or "").strip()
        city = (request.form.get("city") or "").strip()

        if not name:
            flash("Название школы обязательно", "error")
            return redirect(url_for("platform_admin.schools_page"))

        conn = get_db()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(
                "INSERT INTO schools (name, city) VALUES (%s, %s) RETURNING id",
                (name, city or None),
            )
            new_id = cur.fetchone()["id"]
            conn.commit()
            flash("Школа создана", "success")
            return redirect(url_for("platform_admin.school_detail", school_id=new_id))
        except Exception as e:
            conn.rollback()
            flash(f"Ошибка: {e}", "error")
        finally:
            conn.close()

    # список школ
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT id, name, city, created_at FROM schools ORDER BY id DESC")
        schools = cur.fetchall()
        return render_template("platform_schools.html", schools=schools)
    finally:
        conn.close()


@platform_admin_bp.route("/schools/<int:school_id>", methods=["GET", "POST"])
def school_detail(school_id: int):
    if not require_platform_admin():
        return redirect(url_for("login"))

    from app import get_db

    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # школа
        cur.execute("SELECT id, name, city FROM schools WHERE id=%s", (school_id,))
        school = cur.fetchone()
        if not school:
            flash("Школа не найдена", "error")
            return redirect(url_for("platform_admin.schools_page"))

        # создать учителя/админа в школе
        if request.method == "POST" and request.form.get("action") == "create_user":
            username = (request.form.get("username") or "").strip()
            password = (request.form.get("password") or "").strip()
            full_name = (request.form.get("full_name") or "").strip()
            role = (request.form.get("role") or "").strip()

            if role not in ("teacher", "admin"):
                flash("Можно создать только teacher или admin", "error")
                return redirect(url_for("platform_admin.school_detail", school_id=school_id))

            if not username or not password or not full_name:
                flash("Заполни username/password/ФИО", "error")
                return redirect(url_for("platform_admin.school_detail", school_id=school_id))

            try:
                cur.execute(
                    """
                    INSERT INTO users (username, password, role, full_name, school_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (username, generate_password_hash(password), role, full_name, school_id),
                )
                conn.commit()
                flash("Пользователь создан", "success")
                return redirect(url_for("platform_admin.school_detail", school_id=school_id))
            except psycopg2.IntegrityError:
                conn.rollback()
                flash("Такой username уже существует (уникален на всю платформу)", "error")
                return redirect(url_for("platform_admin.school_detail", school_id=school_id))
            except Exception as e:
                conn.rollback()
                flash(f"Ошибка создания пользователя: {e}", "error")
                return redirect(url_for("platform_admin.school_detail", school_id=school_id))

        # список учителей/админов этой школы
        cur.execute(
            """
            SELECT id, username, full_name, role
            FROM users
            WHERE school_id = %s AND role IN ('teacher','admin')
            ORDER BY role, full_name
            """,
            (school_id,),
        )
        staff = cur.fetchall()

        return render_template("platform_school_detail.html", school=school, staff=staff)

    finally:
        conn.close()
