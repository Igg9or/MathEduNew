from flask import Blueprint

# Blueprint для дуэлей
duel_bp = Blueprint(
    'duel',
    __name__,
    template_folder='templates',
    static_folder='static'
)

# Импорт маршрутов после объявления Blueprint
from . import routes
