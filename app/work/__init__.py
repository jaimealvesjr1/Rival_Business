from flask import Blueprint

bp = Blueprint('work', __name__, url_prefix='/work')

from app.work import routes