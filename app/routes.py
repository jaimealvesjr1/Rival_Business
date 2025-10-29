from flask import Blueprint, jsonify, request, redirect, url_for, current_app, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, Jogador, Regiao
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

bp = Blueprint('api', __name__, url_prefix='/api')

# =================================================================
# ROTAS DE AUTENTICAÇÃO
# =================================================================

# 1. Registro de Jogador
@bp.route('/register', methods=['POST'])
def register():
    # Deve estar dentro do contexto para DB, mas request.get_json() funciona fora.
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    regiao_inicial_id_str = data.get('regiao_inicial_id')

    if not all([username, password, regiao_inicial_id_str]):
        return jsonify({"message": "Faltam dados essenciais."}), 400

    try:
        regiao_inicial_id = int(regiao_inicial_id_str)
    except ValueError:
        return jsonify({"message": "ID da localização inválido."}), 400
        
    with current_app.app_context():
        if Jogador.query.filter_by(username=username).first():
            return jsonify({"message": "Usuário já existe."}), 409
        
        regiao_inicial = Regiao.query.get(regiao_inicial_id)
        if not regiao_inicial:
            return jsonify({"message": "Localização inicial não encontrada."}), 400

        hashed_password = generate_password_hash(password)

        new_player = Jogador(
            username=username,
            password_hash=hashed_password,
            regiao_atual_id=regiao_inicial.id,
            # Não criamos Armazém/Progressão ainda, apenas o Jogador
        )

        db.session.add(new_player)
        db.session.commit()
        
        # Loga o usuário após o registro
        login_user(new_player)
        
        return jsonify({"message": "Registro e login bem-sucedidos.", "jogador_id": new_player.id}), 201

# 2. Login de Jogador
@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    with current_app.app_context():
        jogador = Jogador.query.filter_by(username=username).first()

        if jogador and check_password_hash(jogador.password_hash, password):
            login_user(jogador)
            return jsonify({"message": "Login bem-sucedido.", "jogador_id": jogador.id}), 200
        else:
            return jsonify({"message": "Usuário ou senha inválidos."}), 401

# 3. Logout de Jogador
@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logout bem-sucedido."}), 200

# 4. Rota de Perfil (Dashboard)
@bp.route('/profile', methods=['GET'])
@login_required
def profile_dashboard():
    with current_app.app_context():
        jogador = Jogador.query.get(current_user.id)
        # Supondo que a Regiao com ID 1 é a única existente para o MVP
        regiao_atual = Regiao.query.get(jogador.regiao_atual_id) 

        # Renderização do template de dashboard
        return render_template(
            'profile.html', 
            jogador=jogador, 
            regiao_atual=regiao_atual, **footer)