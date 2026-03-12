import math
from datetime import datetime, timedelta
from flask import current_app
from app import db
from app.models import (Jogador, Regiao, TransporteAtivo, Veiculo, RecursoNaMina, HistoricoAcao)
from app.utils import calculate_distance_km

def schedule_transport(jogador, armazem, form_data: dict) -> tuple:
    """
    Função principal para agendar o transporte de recursos da mina para o armazém.
    
    Args:
        jogador: Objeto Jogador (o transportador).
        armazem: Objeto Armazem do jogador.
        form_data: Dicionário com os dados do formulário (regiao_id, tipo_recurso, viagens_{veiculo_id}).
        
    Returns:
        (success: bool, message: str, ultima_data_fim: datetime, custo_total: float, total_viagens: int)
    """

    # 1. Obter dados de origem e recursos pendentes
    try:
        regiao_id = int(form_data.get('regiao_id'))
        tipo_recurso = form_data.get('tipo_recurso')
    except (TypeError, ValueError):
        return (False, "Dados de origem do transporte inválidos.", None, 0.0, 0)
    
    # 2. Buscar TODOS os recursos pendentes nesse grupo
    recursos_para_transportar = RecursoNaMina.query.filter_by(
        jogador_id=jogador.id,
        regiao_id=regiao_id,
        tipo_recurso=tipo_recurso
    ).all()

    if not recursos_para_transportar:
        return (False, "Recursos para transporte não encontrados ou expiraram.", None, 0.0, 0)

    # 3. Calcular a quantidade total pendente
    quantidade_total_pendente = sum(r.quantidade for r in recursos_para_transportar)
    if quantidade_total_pendente <= 0:
        for r in recursos_para_transportar: db.session.delete(r)
        db.session.commit()
        return (False, "Recursos na mina zerados e removidos. Tente novamente.", None, 0.0, 0)

    # 4. CÁLCULO DE TEMPO BASE E DISTÂNCIA
    regiao_origem = Regiao.query.get(regiao_id) 
    regiao_destino = armazem.regiao 
    
    if not regiao_origem:
         return (False, "Região de origem do recurso não encontrada.", None, 0.0, 0)

    distancia_km = calculate_distance_km(regiao_origem.latitude, regiao_origem.longitude, 
                                         regiao_destino.latitude, regiao_destino.longitude)

    # 4.1 Cálculo do Tempo Base (Usando constantes do config.py)
    TEMPO_TRANSPORTE_LOCAL_MIN = current_app.config['TEMPO_TRANSPORTE_LOCAL_MIN']
    CUSTO_MINIMO_FRETE_LOCAL = current_app.config['CUSTO_MINIMO_FRETE_LOCAL']
    VELOCIDADE_BASE_KMH = current_app.config.get('VELOCIDADE_BASE_KMH', 100)
    RECURSO_NA_MINA_EXPIRACAO_MIN = current_app.config['RECURSO_NA_MINA_EXPIRACAO_MIN']
    
    tempo_minutos_base = TEMPO_TRANSPORTE_LOCAL_MIN
    if distancia_km >= 1.0:
        tempo_horas_base = (distancia_km / VELOCIDADE_BASE_KMH) * 2 # Ida e Volta
        tempo_minutos_base = math.ceil(tempo_horas_base * 60)
        tempo_minutos_base = max(TEMPO_TRANSPORTE_LOCAL_MIN, tempo_minutos_base)


    # 5. INICIALIZAÇÃO DE RASTREAMENTO E CUSTOS
    total_viagens_agendadas = 0
    recurso_coberto = 0.0
    custo_frete_total = 0.0
    
    transporte_jobs = [] 
    ultima_data_fim = datetime.utcnow()

    # Mapeia veículos disponíveis AGORA (ignora o sequenciamento na rota)
    veiculos_disponiveis = {v.id: v for v in armazem.frota.all() if not v.transporte_atual}
    veiculo_disponivel_em = {v_id: datetime.utcnow() for v_id in veiculos_disponiveis.keys()}

    # 6. ITERAÇÃO MESTRA: CALCULA CUSTO, TEMPO SEQUENCIAL E CRIA JOBS
    
    for key, viagens_value in form_data.items():
        if key.startswith('viagens_'):
            try:
                veiculo_id = int(key.split('_')[1])
                viagens_requeridas = int(viagens_value)
            except ValueError:
                continue

            if viagens_requeridas <= 0 or veiculo_id not in veiculos_disponiveis:
                continue

            veiculo = veiculos_disponiveis[veiculo_id]
            
            # 6.1 CÁLCULO DE CUSTO PARA ESTE VEÍCULO
            custo_unitario_por_viagem = 0.0
            if distancia_km < 1.0:
                custo_unitario_por_viagem = CUSTO_MINIMO_FRETE_LOCAL 
            else:
                custo_unitario_por_viagem = veiculo.custo_tonelada_km * veiculo.capacidade * distancia_km 
                
            custo_frete_total += custo_unitario_por_viagem * viagens_requeridas
            
            # 6.2 CÁLCULO DE TEMPO AJUSTADO AO VEÍCULO
            tempo_ajuste_velocidade = 1.0 / veiculo.velocidade 
            tempo_total_por_viagem = math.ceil(tempo_minutos_base * tempo_ajuste_velocidade)
            tempo_total_por_viagem = max(TEMPO_TRANSPORTE_LOCAL_MIN, tempo_total_por_viagem)
            
            # 6.3 SEQUENCIAMENTO E CRIAÇÃO
            tempo_inicio = veiculo_disponivel_em[veiculo_id]
            
            for i in range(viagens_requeridas):
                
                recurso_ainda_pendente_na_mina = quantidade_total_pendente - recurso_coberto 
                
                if recurso_ainda_pendente_na_mina <= 0.0:
                    break 
                    
                quantidade_a_enviar = min(veiculo.capacidade, recurso_ainda_pendente_na_mina)
                
                data_fim_viagem = tempo_inicio + timedelta(minutes=tempo_total_por_viagem)
                tempo_inicio = data_fim_viagem 
                
                transporte = TransporteAtivo(
                    jogador_id=jogador.id, veiculo_id=veiculo.id, regiao_origem_id=regiao_origem.id,
                    regiao_destino_id=regiao_destino.id, tipo_recurso=tipo_recurso,
                    quantidade=quantidade_a_enviar, data_fim=data_fim_viagem
                )
                transporte_jobs.append(transporte)
    
                recurso_coberto += quantidade_a_enviar
                total_viagens_agendadas += 1
                
                if data_fim_viagem > ultima_data_fim:
                    ultima_data_fim = data_fim_viagem
            
            veiculo_disponivel_em[veiculo_id] = tempo_inicio 

    # 7. VALIDAÇÕES FINAIS
    if total_viagens_agendadas == 0:
        return (False, "Nenhuma viagem agendada. Selecione os veículos e o número de viagens.", None, 0.0, 0)

    if jogador.dinheiro < custo_frete_total:
        from app.utils import format_currency_python
        return (False, f"Dinheiro insuficiente para cobrir o frete. Custo total: {format_currency_python(custo_frete_total)}", None, 0.0, 0)

    # 8. AÇÕES DE DADOS E COMMIT
    
    # Subtrai o custo TOTAL do frete
    jogador.dinheiro -= custo_frete_total
    
    # Deleta os registros antigos e recalcula o remanescente
    recurso_restante = max(0.0, quantidade_total_pendente - recurso_coberto)
    
    for r in recursos_para_transportar:
        db.session.delete(r)

    if recurso_restante > 0.0:
        novo_remanescente = RecursoNaMina(
            jogador_id=jogador.id,
            regiao_id=regiao_id,
            tipo_recurso=tipo_recurso,
            quantidade=recurso_restante,
            data_expiracao = datetime.utcnow() + timedelta(minutes=RECURSO_NA_MINA_EXPIRACAO_MIN)
        )
        db.session.add(novo_remanescente)
        
    # Registro de Histórico
    descricao_acao = (
        f"Frete agendado para {total_viagens_agendadas} viagens. Custo: R${custo_frete_total:.2f}."
    )
    hist = HistoricoAcao(
        jogador_id=jogador.id,
        tipo_acao='FRETE_COBRADO',
        descricao=descricao_acao,
        dinheiro_delta=-custo_frete_total, 
        gold_delta=0.0
    )

    db.session.add_all(transporte_jobs)
    db.session.add(hist)
    db.session.add(jogador)
    
    # Retorna o status e dados para a rota
    message_to_user = "AVISO: " + str(recurso_restante) + "t permanecerão na mina. Frete cobrado." if recurso_restante > 0 else "Logística agendada com sucesso!"
    return (True, message_to_user, ultima_data_fim, custo_frete_total, total_viagens_agendadas)
