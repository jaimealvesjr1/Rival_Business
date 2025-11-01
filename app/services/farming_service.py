from app import db
from app.models import Jogador, CampoAgricola, PlantioAtivo, HistoricoAcao
from app.services.player_service import calculate_player_factors
from datetime import datetime, timedelta
from flask import current_app
from math import ceil

def start_planting(jogador: Jogador, campo: CampoAgricola, energia_gasta: int):
    """
    Inicia um novo plantio de milho em um campo.
    Retorna (True, "Mensagem") ou (False, "Erro")
    """
    
    # --- 1. Validações (Guards) ---
    if energia_gasta < 10:
        return (False, "Você deve usar no mínimo 10 de energia.")

    if jogador.energia < energia_gasta:
        return (False, f"Energia insuficiente. Você tem {jogador.energia}.")

    if campo.data_descanso_fim and campo.data_descanso_fim > datetime.utcnow():
        tempo_restante = (campo.data_descanso_fim - datetime.utcnow()).total_seconds()
        return (False, f"Este campo está descansando. Tente novamente em {tempo_restante // 60} minutos.")

    if campo.plantios_ativos.count() >= current_app.config['FARMING_FIELD_MAX_SLOTS']:
        return (False, "Este campo já atingiu o limite de plantios simultâneos (2 slots).")

    # Custo proporcional (Regra 1)
    custo_dinheiro = current_app.config['FARMING_COST_MONEY_PER_10_ENERGY'] * (energia_gasta / 10.0)
    
    fatores = calculate_player_factors(jogador)
    custo_energia_real = ceil(energia_gasta * (1.0 - fatores['desconto_energia'])) # Bônus de Saúde

    if jogador.dinheiro < custo_dinheiro:
        return (False, f"Dinheiro insuficiente. Você precisa de R$ {custo_dinheiro:,.2f} para plantar.")

    try:
        # --- 2. Calcular Produção (Regra 5: Bônus Regional) ---
        # Usamos 'indice_educacao' para agricultura (melhores técnicas)
        bonus_regional = 1.0 + (campo.regiao.indice_educacao / 10.0) 
        
        milho_base = current_app.config['MILHO_POR_ENERGIA'] * (energia_gasta / 10.0)
        quantidade_final = milho_base * bonus_regional
        
        # --- 3. Calcular Tempo de Crescimento (Regra 2) ---
        tempo_crescimento = current_app.config['FARMING_GROW_TIME_MINUTES']
        data_fim = datetime.utcnow() + timedelta(minutes=tempo_crescimento)
        
        # --- 4. Criar o PlantioAtivo ---
        novo_plantio = PlantioAtivo(
            jogador_id=jogador.id,
            campo_id=campo.id,
            data_fim=data_fim,
            quantidade_produzida=quantidade_final
        )
        
        # --- 5. Atualizar Jogador e Campo ---
        jogador.dinheiro -= custo_dinheiro
        jogador.energia -= custo_energia_real
        jogador.last_status_update = datetime.utcnow() # Reseta o timer de regeneração de energia
        
        campo.usos_restantes -= 1
        
        # Lógica de descanso REMOVIDA daqui. Será aplicada no background_tasks após a colheita.
        
        db.session.add(novo_plantio)
        db.session.add(jogador)
        db.session.add(campo)
        
        return (True, f"Plantio de {quantidade_final:.0f}t de Milho iniciado! Colheita em {tempo_crescimento} minutos.")

    except Exception as e:
        db.session.rollback()
        return (False, f"Erro ao iniciar plantio: {e}")
