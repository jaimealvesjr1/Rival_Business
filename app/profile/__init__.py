from flask import Blueprint

# Cria uma instância do Blueprint para o módulo 'profile'
bp = Blueprint('profile', __name__)

from app.profile import routes