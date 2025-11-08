from flask import request, jsonify, render_template
from duel import duel_bp
from duel.models import Duel, DuelRound, DuelAnswer
from duel.ai import evaluate_pair

@duel_bp.route('/teacher')
def teacher_panel():
    return render_template('teacher.html')

@duel_bp.route('/student')
def student_panel():
    return render_template('student.html')

@duel_bp.route('/api/create', methods=['POST'])
def create_duel():
    from app import db  # 👈 импорт внутри функции
    data = request.json
    duel = Duel(
        name=data.get('name'),
        subject=data.get('subject'),
        teacher_id=data.get('teacher_id'),
        class_id=data.get('class_id')
    )
    db.session.add(duel)
    db.session.commit()
    return jsonify({"status": "ok", "duel_id": duel.id})

@duel_bp.route('/api/judge', methods=['POST'])
def judge_round():
    data = request.json
    result = evaluate_pair(
        question=data['question'],
        answer_a=data['answer_a'],
        answer_b=data['answer_b']
    )
    return jsonify(result)
