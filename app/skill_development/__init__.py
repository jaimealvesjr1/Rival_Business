from flask import Blueprint

bp = Blueprint('skill_development', __name__, url_prefix='/skill')

from app.skill_development import routes