from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, current_user, logout_user, login_required
from app import db, bcrypt
from app.auth import bp # Importa o Blueprint
from app.auth.forms import RegistrationForm, LoginForm
from app.models import Jogador, Regiao
from urllib.parse import urlparse as url_parse
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

# ----------------------------------------------------
# ROTA DE REGISTRO
# ----------------------------------------------------
@bp.route('/register', methods=['GET', 'POST'])
def register():
    # Se o usuário já estiver logado, redireciona para a página principal
    if current_user.is_authenticated:
        return redirect(url_for('index')) # 'index' é a rota definida em app/__init__.py

    form = RegistrationForm()
    
    if form.validate_on_submit():
        try:
            # 1. Obter a localização inicial
            # O jogador precisa estar em alguma localização para ter o ID de Foreign Key preenchido
            regiao_inicial = Regiao.query.first()
            if not regiao_inicial:
                # Caso o banco de dados esteja vazio, evita o erro de Foreign Key
                flash('Não há regiões cadastradas. Tente novamente mais tarde.', 'danger')
                return redirect(url_for('auth.register'))

            # 2. Criação do novo jogador
            new_player = Jogador(
                username=form.username.data,
                regiao_residencia_id=regiao_inicial.id,
                regiao_atual_id=regiao_inicial.id
            )
            
            # Define a senha de forma segura (hashing)
            new_player.set_password(form.password.data)
            
            # 3. Adiciona ao banco de dados e salva
            db.session.add(new_player)
            db.session.commit()

            flash('Sua conta foi criada! Você já pode fazer login.', 'success')
            return redirect(url_for('auth.login'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Ocorreu um erro inesperado ao registrar: {e}', 'danger')
            return redirect(url_for('auth.register'))
            
    return render_template('auth/register.html', title='Registro', form=form, **footer)


# ----------------------------------------------------
# ROTA DE LOGIN
# ----------------------------------------------------
@bp.route('/login', methods=['GET', 'POST'])
def login():
    # Se o usuário já estiver logado, redireciona para a página principal
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    
    if form.validate_on_submit():
        # Busca o jogador pelo nome de usuário
        jogador = Jogador.query.filter_by(username=form.username.data).first()
        
        # Verifica se o jogador existe E se a senha está correta
        if jogador is None or not jogador.check_password(form.password.data):
            flash('Login Invalido. Verifique seu nome de usuário e senha.', 'danger')
            return redirect(url_for('auth.login'))

        # Faz o login do usuário
        login_user(jogador, remember=form.remember.data)
        
        # Redirecionamento após o login (útil para rotas protegidas)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
            
        flash(f'Bem-vindo, {jogador.username}!', 'success')
        return redirect(next_page)
        
    return render_template('auth/login.html', title='Login', form=form, **footer)


# ----------------------------------------------------
# ROTA DE LOGOUT
# ----------------------------------------------------
@bp.route('/logout')
@login_required # Garante que apenas usuários logados possam acessar
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))
