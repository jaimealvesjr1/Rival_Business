from flask import Blueprint

bp = Blueprint('game_actions', __name__, url_prefix='/game')

from app.game_actions import routes