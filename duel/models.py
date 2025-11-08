from datetime import datetime
import typing

if typing.TYPE_CHECKING:
    from app import db

class Duel(db.Model):
    __tablename__ = 'duel'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    subject = db.Column(db.String(50))
    teacher_id = db.Column(db.Integer)
    class_id = db.Column(db.Integer)
    status = db.Column(db.String(20), default="waiting")  # waiting / active / finished
    duel_type = db.Column(db.String(20), default="humanities")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DuelRound(db.Model):
    __tablename__ = 'duel_round'
    id = db.Column(db.Integer, primary_key=True)
    duel_id = db.Column(db.Integer, db.ForeignKey('duel.id'))
    round_number = db.Column(db.Integer)
    pairs = db.Column(db.JSON)  # [{"a":1,"b":2,"question":"..."}]
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DuelAnswer(db.Model):
    __tablename__ = 'duel_answer'
    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.Integer, db.ForeignKey('duel_round.id'))
    user_id = db.Column(db.Integer)
    question = db.Column(db.Text)
    answer_text = db.Column(db.Text)
    ai_score = db.Column(db.Float)
    ai_feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
