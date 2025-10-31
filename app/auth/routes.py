from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, current_user, logout_user, login_required
from app import db, bcrypt
from app.auth import bp
from app.auth.forms import RegistrationForm, LoginForm
from app.models import Jogador, Regiao, Armazem, TipoVeiculo, Veiculo
from urllib.parse import urlparse as url_parse
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

# ----------------------------------------------------
# ROTA DE REGISTRO
# ----------------------------------------------------
@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm()
    
    if form.validate_on_submit():
        try:
            regiao_inicial = Regiao.query.first()
            regiao_id_selecionada = form.regiao_inicial_id.data
            regiao_selecionada = Regiao.query.get(regiao_id_selecionada)
            if not regiao_selecionada:
                 # Tratar o caso em que a seleção é inválida ou o placeholder (-1)
                flash('Região de início inválida. Tente novamente.', 'danger')
                return redirect(url_for('auth.register'))

            # 2. Criação do novo jogador
            new_player = Jogador(
                username=form.username.data,
                regiao_residencia_id=regiao_selecionada.id,
                regiao_atual_id=regiao_selecionada.id
            )
            new_player.set_password(form.password.data)
                        
            # 3. Adiciona ao banco de dados e salva
            db.session.add(new_player)
            db.session.flush()
                       
            # 1. Cria o Armazém
            armazem = Armazem(jogador_id=new_player.id, regiao_id=regiao_selecionada.id)
            db.session.add(armazem)
            db.session.flush()

            rodotrem_tipo = TipoVeiculo.query.filter_by(tipo_veiculo='rodotrem').first()

            if rodotrem_tipo:
                veiculo_inicial = Veiculo(
                    armazem_id=armazem.id,
                    nome=rodotrem_tipo.nome_display,
                    tipo_veiculo=rodotrem_tipo.tipo_veiculo,
                    capacidade=rodotrem_tipo.capacidade,
                    velocidade=rodotrem_tipo.velocidade,
                    custo_tonelada_km=rodotrem_tipo.custo_tonelada_km,
                    validade_dias=rodotrem_tipo.validade_dias,
                    nivel_especializacao_req=rodotrem_tipo.nivel_especializacao_req
                )
                db.session.add(veiculo_inicial)

            db.session.commit()

            flash('Sua conta foi criada! Você já pode fazer login.', 'success')
            return redirect(url_for('auth.login'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Ocorreu um erro inesperado ao registrar: {e}', 'danger')
            return redirect(url_for('auth.register'))
            
    return render_template('auth/register.html', title='Registro', form=form, **footer)

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

@bp.route('/logout')
@login_required # Garante que apenas usuários logados possam acessar
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))
