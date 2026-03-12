from flask import render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.work import bp
from app.models import ViagemAtiva, CampoAgricola
from app.game_actions.forms import OpenCompanyForm, OpenCampoForm 
from config import Config
from datetime import datetime

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

@bp.route('/')
@login_required
def work_dashboard():
    jogador = current_user
    regiao = jogador.regiao_atual
    viagem_ativa = ViagemAtiva.query.filter_by(jogador_id=jogador.id).first()

    if viagem_ativa:
        flash(f"Você está em viagem para {viagem_ativa.destino.nome} e não pode trabalhar!", 'warning')
        return redirect(url_for('map.view_map'))
    
    if not regiao:
        flash("Você precisa estar em uma localização para acessar o trabalho.", 'danger')
        return redirect(url_for('profile.view_profile'))
        
    empresas_na_regiao = regiao.empresas.all()
    
    energia_disponivel = jogador.energia
    energia_int = int(energia_disponivel)
    opcoes_energia = list(range(10, energia_int + 1, 10))
    
    fabricas_estatais = [e for e in empresas_na_regiao if e.tipo == 'estatal']
    fabricas_privadas = [e for e in empresas_na_regiao if e.tipo == 'privada']

    campos_na_regiao = CampoAgricola.query.filter_by(regiao_id=regiao.id).all()
    farm_slots_max = current_app.config['FARMING_FIELD_MAX_SLOTS']
    farm_max_uses = current_app.config['FARMING_FIELD_MAX_USES']
    
    form_empresa = OpenCompanyForm()
    form_campo = OpenCampoForm()
    GROW_TIME_MINUTES = current_app.config['FARMING_GROW_TIME_MINUTES']

    custos_empresa = jogador.get_open_company_cost()
    residente = regiao.id == jogador.regiao_residencia_id
    limite_empresas_atingido = len(jogador.empresas_proprias) >= jogador.get_max_empresas()
    
    pode_abrir_empresa = (
        jogador.dinheiro >= custos_empresa['money'] and 
        jogador.gold >= custos_empresa['gold'] and
        jogador.nivel >= 5 and
        residente and 
        not limite_empresas_atingido
    )

    custos_campo = jogador.get_open_campo_cost()
    limite_campos_atingido = len(jogador.campos_proprios) >= jogador.get_max_campos()
    
    pode_comprar_campo = (
        jogador.dinheiro >= custos_campo['money'] and 
        jogador.gold >= custos_campo['gold'] and 
        jogador.nivel >= 2 and 
        residente and
        not limite_campos_atingido
    )

    return render_template('work/work_dashboard.html',
                           title=f'Trabalho em {regiao.nome}',
                           jogador=jogador,
                           regiao=regiao,
                           fabricas_estatais=fabricas_estatais,
                           fabricas_privadas=fabricas_privadas,
                           campos_na_regiao=campos_na_regiao,
                           opcoes_energia=opcoes_energia,
                           FARMING_COST_MONEY_PER_10_ENERGY=current_app.config['FARMING_COST_MONEY_PER_10_ENERGY'],
                           FARMING_FIELD_MAX_SLOTS=current_app.config['FARMING_FIELD_MAX_SLOTS'],
                           FARMING_FIELD_MAX_USES=current_app.config['FARMING_FIELD_MAX_USES'],
                           farm_slots_max=farm_slots_max,
                           farm_max_uses=farm_max_uses,
                           form_empresa=form_empresa, 
                           form_campo=form_campo,
                           GROW_TIME_MINUTES=GROW_TIME_MINUTES,
                           custos_empresa=custos_empresa,
                           custos_campo=custos_campo,
                           residente=residente,
                           limite_empresas_atingido=limite_empresas_atingido,
                           limite_campos_atingido=limite_campos_atingido,
                           pode_abrir_empresa=pode_abrir_empresa,
                           pode_comprar_campo=pode_comprar_campo,
                           **footer)
