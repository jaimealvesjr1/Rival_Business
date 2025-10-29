from flask import Blueprint

# Cria uma instância do Blueprint para o módulo 'auth'
bp = Blueprint('auth', __name__)

# Importa as rotas para que o Blueprint as registre
from app.auth import routes
