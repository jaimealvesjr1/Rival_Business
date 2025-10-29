from flask import Blueprint

bp = Blueprint('warehouse', __name__, url_prefix='/warehouse')

from app.warehouse import routes