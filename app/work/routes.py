from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.work import bp
from app.models import ViagemAtiva, RecursoNaMina, TransporteAtivo
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
        
    # Busca todas as empresas (estatais e privadas) na localização
    empresas_na_regiao = regiao.empresas.all()
    
    # Prepara as opções de energia (de 10 em 10, limitado ao jogador)
    energia_disponivel = jogador.energia
    energia_int = int(energia_disponivel)
    opcoes_energia = list(range(10, energia_int + 1, 10))
    
    # Exemplo: Simular XP de Outras Fábricas (para o seu layout de referência)
    fabricas_estatais = [e for e in empresas_na_regiao if e.tipo == 'estatal']
    fabricas_privadas = [e for e in empresas_na_regiao if e.tipo == 'privada']

    return render_template('work/work_dashboard.html',
                           title=f'Trabalho em {regiao.nome}',
                           jogador=jogador,
                           regiao=regiao,
                           fabricas_estatais=fabricas_estatais,
                           fabricas_privadas=fabricas_privadas,
                           opcoes_energia=opcoes_energia, **footer)
