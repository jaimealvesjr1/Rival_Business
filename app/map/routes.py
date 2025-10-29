from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.map import bp
from app.utils import calculate_distance_km
from app.models import Regiao, Jogador, ViagemAtiva
from math import ceil
from datetime import datetime
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

HORA_POR_KM = 100 # A cada 100km gasta 1h (1h / 100km = 0.01h/km)
CUSTO_POR_KM = 5.0 # R$5 por KM

@bp.route('/')
@login_required
def view_map():
    # Recarrega o jogador para o estado mais fresco
    jogador = Jogador.query.get(current_user.id) 
    regiao_atual = jogador.regiao_atual

    viagem_ativa = ViagemAtiva.query.filter_by(jogador_id=jogador.id).first()

    todas_regioes = Regiao.query.all()

    opcoes_viagem_calculadas = []

    if not viagem_ativa:
        
        aceleracao_percentual = regiao_atual.indice_desenvolvimento
        fator_aceleracao = 1.0 - (aceleracao_percentual / 100.0)
        
        for destino in todas_regioes:
            
            opcao = {'regiao': destino} # Estrutura base

            # Se for a região atual, não calcula distância/custo
            if destino.id == regiao_atual.id:
                opcao['status'] = 'Atual'
                # Não haverá 'distancia_bruta', etc.
            else:
                opcao['status'] = 'Disponível'
                
                distancia_bruta = calculate_distance_km(
                    regiao_atual.latitude, regiao_atual.longitude, 
                    destino.latitude, destino.longitude
                )

                distancia_efetiva = round(distancia_bruta * fator_aceleracao, 2)
                tempo_horas = ceil(distancia_efetiva / HORA_POR_KM)
                custo_total = round(distancia_efetiva * CUSTO_POR_KM, 2)
                
                opcao.update({
                    'distancia_bruta': distancia_bruta,
                    'distancia_efetiva': distancia_efetiva,
                    'tempo_horas': tempo_horas,
                    'custo_total': custo_total,
                    'pode_viajar': jogador.dinheiro >= custo_total
                })
            
            opcoes_viagem_calculadas.append(opcao)
    else:
        # Se estiver viajando, apenas lista todas as regiões
        opcoes_viagem_calculadas = [{'regiao': r} for r in todas_regioes]

    if viagem_ativa:
        tempo_restante = viagem_ativa.data_fim - datetime.utcnow()
        tempo_restante_segundos = int(tempo_restante.total_seconds()) if tempo_restante.total_seconds() > 0 else 0
    else:
        tempo_restante_segundos = 0
    
    return render_template('map/view_map.html',
                           title='Mapa de Viagem',
                           jogador=jogador,
                           regiao_atual=regiao_atual,
                           viagem_ativa=viagem_ativa,
                           tempo_restante_segundos=tempo_restante_segundos,
                           opcoes_viagem=opcoes_viagem_calculadas, **footer)
