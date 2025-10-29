from flask import Blueprint, render_template, current_app
from app.models import Regiao
from flask_login import current_user
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}
main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=['GET'])
def index():
    with current_app.app_context():
        regioes = Regiao.query.all()
    
    return render_template('index.html', regioes=regioes, is_authenticated=current_user.is_authenticated, **footer)
