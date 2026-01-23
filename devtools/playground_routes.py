from flask import Blueprint, request, jsonify
import requests
from task_generator import TaskGenerator

print("🔥 playground_routes.py LOADED")
# Blueprint
playground_bp = Blueprint("template_playground", __name__)

# --- НАСТРОЙКИ ---
LOCAL_BASE_URL = "http://127.0.0.1:5000"


def call_check_answer(answer, correct_answer, answer_type="numeric"):
    """
    Переиспользуем существующий /api/check_answer БЕЗ изменений
    """
    try:
        resp = requests.post(
            f"{LOCAL_BASE_URL}/api/check_answer",
            json={
                "answer": answer,
                "correct_answer": correct_answer,
                "answer_type": answer_type
            },
            timeout=10
        )
        return resp.json()
    except Exception as e:
        return {"error": f"check_answer failed: {e}"}


def call_ai_full_solution(question, student_answer, student_grade):
    """
    Переиспользуем существующий /api/ai_full_solution БЕЗ изменений
    """
    try:
        resp = requests.post(
            f"{LOCAL_BASE_URL}/api/ai_full_solution",
            json={
                "question": question,
                "student_answer": student_answer,
                "student_grade": student_grade
            },
            timeout=60
        )
        data = resp.json()
        return data.get("ai_verdict")
    except Exception as e:
        return {"error": f"ai_full_solution failed: {e}"}


@playground_bp.route("/preview_templates", methods=["POST"])
def preview_templates():
    print("🔥 preview_templates PREVIEW ONLY")

    data = request.get_json(force=True)
    templates = data.get("templates", [])

    if not isinstance(templates, list) or not templates:
        return jsonify({
            "status": "error",
            "message": "templates must be a non-empty array"
        }), 400

    preview = []

    for index, template in enumerate(templates, start=1):
        try:
            # Генерируем ОДИН вариант (по умолчанию)
            variant = TaskGenerator.generate_task_variant(template)
            question = variant.get("question", "")
        except Exception as e:
            question = f"❌ Ошибка генерации: {e}"

        preview.append({
            "index": index,
            "question": question
        })

    return jsonify({
        "status": "ok",
        "preview": preview
    })


