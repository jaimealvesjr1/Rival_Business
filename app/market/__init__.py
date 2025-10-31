from flask import Blueprint

bp = Blueprint('market', __name__, url_prefix='/market')

from app.market import routes