from flask import render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.profile import bp
from app.models import Jogador, ViagemAtiva, PedidoResidencia, Regiao
from datetime import datetime, timezone
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

@bp.route('/profile')
@login_required
def view_profile():
    from app.models import Jogador
    jogador = Jogador.query.get(current_user.id)

    if jogador is None:
        from flask_login import logout_user
        logout_user()
        return redirect(url_for('auth.login'))
    
    rank_regioes = Regiao.query.order_by(
        Regiao.indice_desenvolvimento.desc(),
        Regiao.indice_educacao.desc(),
        Regiao.indice_saude.desc()
    ).all()

    rank_jogadores = Jogador.query.order_by(
        Jogador.experiencia.desc(),
        Jogador.dinheiro.desc()
    ).all()
    
    treino_ativo = jogador.treino_ativo 
    tempo_restante_segundos = 0
    
    if treino_ativo and treino_ativo.data_fim:
        tempo_restante = treino_ativo.data_fim - datetime.utcnow()
        if tempo_restante.total_seconds() > 0:
            tempo_restante_segundos = int(tempo_restante.total_seconds())
    
    viagem_ativa = ViagemAtiva.query.filter_by(jogador_id=jogador.id).first()
    pedido_ativo = PedidoResidencia.query.filter_by(jogador_id=jogador.id).first()
    tempo_restante_residencia = 0

    if pedido_ativo and pedido_ativo.data_aprovacao:
        tempo_restante = pedido_ativo.data_aprovacao - datetime.utcnow()
        if tempo_restante.total_seconds() > 0:
            tempo_restante_residencia = int(tempo_restante.total_seconds())
    
    try:
        from app.background_tasks import regenerate_player_status
        regenerate_player_status(current_app._get_current_object()) 
    except Exception as e:
        current_app.logger.error(f"Erro ao forçar regeneração na view profile: {e}")

    return render_template('profile/view_profile.html',
                            title='Meu Perfil',
                            jogador=jogador,
                            treino_ativo=treino_ativo,
                            tempo_restante_segundos=tempo_restante_segundos,
                            viagem_ativa=viagem_ativa,
                            pedido_ativo=pedido_ativo,
                            tempo_restante_residencia=tempo_restante_residencia,
                            rank_regioes=rank_regioes,
                            rank_jogadores=rank_jogadores, **footer)
