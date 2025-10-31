from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.manage import bp
from app.manage.forms import RegionForm, PlayerForm, CompanyAdminForm, PlayerEditForm, RegionEditForm, CompanyEditForm
from werkzeug.security import generate_password_hash

from app.manage.forms import RegionForm, PlayerForm, CompanyAdminForm
from app.models import Regiao, Jogador, Empresa, TipoVeiculo
from functools import wraps
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

def admin_required(f):
    @login_required
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Acesso negado: Você não tem permissão de administrador.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@admin_required
def manage_dashboard():
    # 1. Obter todas as listas
    jogadores = Jogador.query.all()
    regioes = Regiao.query.all()
    empresas = Empresa.query.all()
    tipos_veiculos = TipoVeiculo.query.all()
    
    return render_template('manage/manage_dashboard.html',
                           title='Painel de Gestão',
                           jogadores=jogadores,
                           regioes=regioes,
                           empresas=empresas,
                           tipos_veiculos=tipos_veiculos, **footer)

@bp.route('/create_region', methods=['GET', 'POST'])
@admin_required 
def create_region():
    form = RegionForm()
    
    if form.validate_on_submit():
        try:
            nova_regiao = Regiao(
                nome=form.nome.data,
                latitude=form.latitude.data,
                longitude=form.longitude.data,
                
                reserva_ouro_max=form.reserva_ouro_max.data,
                reserva_ferro_max=form.reserva_ferro_max.data
            )
            
            db.session.add(nova_regiao)
            db.session.flush()

            recursos_estatais = [
                {'nome': 'Mina de Ouro', 'produto': 'ouro', 'taxa_lucro': 0.30, 'reserva_key': 'reserva_ouro'},
                {'nome': 'Mina de Ferro', 'produto': 'ferro', 'taxa_lucro': 0.30, 'reserva_key': 'reserva_ferro'}
            ]

            for recurso in recursos_estatais:

                empresa_estatal = Empresa(
                    regiao_id=nova_regiao.id,
                    nome=f"{recurso['nome']} - {nova_regiao.nome}",
                    tipo='estatal',
                    produto=recurso['produto'],
                    taxa_lucro=recurso['taxa_lucro'], 
                    dinheiro=0.0
                )
                db.session.add(empresa_estatal)

            db.session.commit()
            flash(f'Localização "{nova_regiao.nome}" e estatais criadas com sucesso!', 'success')
            return redirect(url_for('manage.manage_dashboard'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar localização: {e}', 'danger')
            
    return render_template('manage/create_region.html', title='Criar Nova Localização', form=form, **footer)

@bp.route('/edit_region/<int:region_id>', methods=['GET', 'POST'])
@admin_required
def edit_region(region_id):
    regiao = Regiao.query.get_or_404(region_id)
    form = RegionEditForm(obj=regiao) 

    if form.validate_on_submit():
        try:
            form.populate_obj(regiao)
            
            # Recalcula a taxa de imposto caso o admin tenha mudado o índice
            regiao.calcular_taxa_imposto() 
            
            db.session.add(regiao)
            db.session.commit()
            
            flash(f'Localização "{regiao.nome}" atualizada com sucesso!', 'success')
            return redirect(url_for('manage.manage_dashboard'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao editar localização: {e}', 'danger')
            
    return render_template('manage/edit_region.html', title=f'Editar {regiao.nome}', form=form, regiao=regiao, **footer)

@bp.route('/create_player', methods=['GET', 'POST'])
@admin_required
def create_player():
    form = PlayerForm()
    
    if form.validate_on_submit():
        regiao_destino = Regiao.query.get(form.regiao_id.data)
        if not regiao_destino:
            flash("Localização inicial inválida.", 'danger')
            return redirect(url_for('manage.create_player'))

        try:
            novo_jogador = Jogador(
                username=form.username.data,
                is_admin=form.is_admin.data,
                regiao_residencia_id=regiao_destino.id,
                regiao_atual_id=regiao_destino.id,
                # Outros defaults do Jogador serão aplicados
            )
            novo_jogador.set_password(form.password.data)
            
            db.session.add(novo_jogador)
            db.session.commit()
            
            flash(f'Jogador "{novo_jogador.username}" criado com sucesso! Admin: {novo_jogador.is_admin}', 'success')
            return redirect(url_for('manage.manage_dashboard'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar jogador: {e}', 'danger')
            
    return render_template('manage/create_player.html', title='Criar Novo Jogador', form=form, **footer)

@bp.route('/edit_player/<int:player_id>', methods=['GET', 'POST'])
@admin_required
def edit_player(player_id):
    jogador = Jogador.query.get_or_404(player_id)
    form = PlayerEditForm(obj=jogador) # Carrega os dados do jogador no formulário

    if form.validate_on_submit():
        try:
            # Atualiza todos os campos do formulário (exceto a senha)
            form.populate_obj(jogador) 
            
            # Atualiza a senha se for fornecida
            if form.new_password.data:
                jogador.set_password(form.new_password.data) 
            
            # Adiciona o jogador à sessão e salva
            db.session.add(jogador)
            db.session.commit()
            
            flash(f'Jogador "{jogador.username}" atualizado com sucesso!', 'success')
            return redirect(url_for('manage.manage_dashboard'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao editar jogador: {e}', 'danger')
            
    # Para o GET, renderiza o formulário com os dados do jogador
    return render_template('manage/edit_player.html', title=f'Editar {jogador.username}', form=form, jogador=jogador, **footer)

@bp.route('/create_company', methods=['GET', 'POST'])
@admin_required
def create_company():
    form = CompanyAdminForm()
    
    if form.validate_on_submit():
        regiao_destino = Regiao.query.get(form.regiao_id.data)
        proprietario = Jogador.query.get(form.proprietario_id.data)

        if not regiao_destino or not proprietario:
            flash("Localização ou Proprietário inválido.", 'danger')
            return redirect(url_for('manage.create_company'))
        
        try:
            nova_empresa = Empresa(
                regiao=regiao_destino, 
                nome=form.nome.data,
                tipo='privada',
                produto=form.produto.data,
                proprietario_id=proprietario.id, 
                taxa_lucro=form.taxa_lucro.data
            )
            
            db.session.add(nova_empresa)
            db.session.commit()
            
            flash(f"Empresa '{nova_empresa.nome}' criada para {proprietario.username}!", 'success')
            return redirect(url_for('manage.manage_dashboard'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar empresa: {e}', 'danger')
            
    return render_template('manage/create_company.html', title='Criar Nova Empresa', form=form, **footer)

@bp.route('/edit_company/<int:company_id>', methods=['GET', 'POST'])
@admin_required
def edit_company(company_id):
    empresa = Empresa.query.get_or_404(company_id)
    form = CompanyEditForm(obj=empresa) 
    
    # Preencher proprietário_id no formulário se não for None
    if empresa.proprietario_id:
        form.proprietario_id.data = empresa.proprietario_id

    if form.validate_on_submit():
        try:
            form.populate_obj(empresa)

            # Garante que o proprietário_id seja NULL se o tipo for 'estatal' (ID 0)
            if form.proprietario_id.data == 0 and form.tipo.data == 'estatal':
                 empresa.proprietario_id = None
            
            db.session.add(empresa)
            db.session.commit()
            
            flash(f'Empresa "{empresa.nome}" atualizada com sucesso!', 'success')
            return redirect(url_for('manage.manage_dashboard'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao editar empresa: {e}', 'danger')
            
    return render_template('manage/edit_company.html', title=f'Editar {empresa.nome}', form=form, empresa=empresa, **footer)

@bp.route('/delete/<string:model_name>/<int:id>', methods=['POST'])
@admin_required
def delete_data(model_name, id):
    
    model_map = {
        'jogador': Jogador,
        'regiao': Regiao,
        'empresa': Empresa
    }

    Model = model_map.get(model_name)
    if not Model:
        flash("Modelo de dados inválido para exclusão.", 'danger')
        return redirect(url_for('manage.manage_dashboard'))

    objeto = Model.query.get_or_404(id)
    nome = getattr(objeto, 'username', getattr(objeto, 'nome', f'ID {id}')) # Nome amigável
    
    try:
        # Nota: O SQLAlchemy deve cuidar de Foreign Keys com cascade, mas é bom testar
        db.session.delete(objeto)
        db.session.commit()
        flash(f'{model_name.capitalize()} "{nome}" excluído com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir {model_name}: {e}', 'danger')
        
    return redirect(url_for('manage.manage_dashboard'))
