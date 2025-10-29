from flask import Blueprint

# O prefixo /manage será usado para as ações administrativas customizadas
bp = Blueprint('manage', __name__, url_prefix='/manage')

from app.manage import routes
