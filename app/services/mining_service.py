from app import db
from app.models import Jogador, Empresa, Regiao, HistoricoAcao, RecursoNaMina
from app.services.player_service import calculate_player_factors
from app.utils import format_currency_python
from datetime import datetime, timedelta
from flask import current_app
from math import ceil

def get_money_production(xp_trabalho):
    """Calcula o valor total em dinheiro gerado pela ação, escalado pela XP."""
    # Esta função estava no app/game_actions/routes.py
    base_production = 5000 
    xp_max_level = current_app.config['XP_MAX_LEVEL']
    multiplicador = (1 + (xp_trabalho / xp_max_level) * 59.2) # Ajuste linear simplificado

    return base_production * multiplicador

def mine_gold_action(jogador: Jogador, empresa: Empresa, regiao: Regiao, energia_gasta: int):
    """
    Executa a lógica de negócio de minerar ouro.
    Retorna (sucesso: bool, mensagem: str)
    """

    # --- 1. CÁLCULO DE FATORES (Agora do Serviço) ---
    fatores = calculate_player_factors(jogador)
    desconto_energia = fatores['desconto_energia']
    multiplicador_xp_educacao = fatores['multiplicador_xp_educacao']
    desconto_imposto = fatores['desconto_imposto']

    # --- 2. APLICAÇÃO DOS BÔNUS/DESCONTOS ---
    energia_gasta_real = ceil(energia_gasta * (1.0 - desconto_energia)) 
    taxa_imposto_regional = regiao.taxa_imposto_geral
    taxa_imposto_efetiva = taxa_imposto_regional * (1.0 - desconto_imposto)

    # C. CÁLCULO DE GANHO (Usando as configs)
    fator_reducao = current_app.config['FATOR_REDUCAO_DINHEIRO']
    ouro_por_energia = current_app.config['OURO_POR_ENERGIA']
    dinheiro_total_gerado = get_money_production(jogador.experiencia_trabalho) * (energia_gasta / 10.0) * fator_reducao

    # D. DISTRIBUIÇÃO USANDO TAXA EFETIVA
    valor_imposto_dinheiro = dinheiro_total_gerado * taxa_imposto_efetiva 
    valor_imposto_gold = ouro_por_energia * energia_gasta * taxa_imposto_efetiva

    # --- CÁLCULO DA PRODUTIVIDADE E GANHOS ---
    taxa_lucro_empresa = empresa.taxa_lucro

    # 1. Imposto (Pago ao governo/região)
    valor_imposto_dinheiro = dinheiro_total_gerado * taxa_imposto_efetiva # << USANDO TAXA EFETIVA
    valor_imposto_gold = ouro_por_energia * energia_gasta * taxa_imposto_efetiva # << USANDO TAXA EFETIVA

    # 2. Lucro da Empresa (Pago à empresa)
    valor_lucro_empresa_dinheiro = dinheiro_total_gerado * taxa_lucro_empresa
    valor_lucro_empresa_gold = ouro_por_energia * energia_gasta * taxa_lucro_empresa

    # C. Dinheiro Líquido para o Jogador
    dinheiro_liquido_jogador = dinheiro_total_gerado - valor_imposto_dinheiro - valor_lucro_empresa_dinheiro
    gold_liquido_jogador = (ouro_por_energia * energia_gasta) - valor_imposto_gold - valor_lucro_empresa_gold

    # XP
    xp_trabalho_ganho_final = current_app.config['XP_TRABALHO_POR_ENERGIA'] * energia_gasta
    xp_geral_ganho_final = current_app.config['XP_GERAL_POR_ENERGIA'] * energia_gasta * multiplicador_xp_educacao

    if dinheiro_liquido_jogador < 0 or gold_liquido_jogador < 0:
        dinheiro_liquido_jogador = max(0.0, dinheiro_liquido_jogador)
        gold_liquido_jogador = max(0.0, gold_liquido_jogador)
        # Não é um erro fatal, mas um aviso
        # return (False, 'As taxas e lucros excedem o valor gerado. Trabalhe em outra região ou melhore sua XP.')

    # D. Subtração de Reserva
    esgotamento_total = current_app.config['ESGOTAMENTO_POR_ENERGIA'] * energia_gasta 
    regiao.reserva_ouro = max(0.0, regiao.reserva_ouro - esgotamento_total)

    # --- ATUALIZAÇÃO DO JOGADOR, EMPRESA E REGIÃO ---

    # 1. Jogador
    jogador.experiencia_trabalho += xp_trabalho_ganho_final
    jogador.experiencia += xp_geral_ganho_final
    jogador.energia -= energia_gasta_real # << USANDO ENERGIA REAL
    jogador.dinheiro += dinheiro_liquido_jogador
    jogador.gold += gold_liquido_jogador

    levelup = jogador.check_level_up()

    # 2. Empresa (Proprietário ou Estatal)
    if empresa.tipo == 'privada':
        proprietario = empresa.proprietario
        if proprietario:
            proprietario.dinheiro += valor_lucro_empresa_dinheiro
            proprietario.gold += valor_lucro_empresa_gold 
            db.session.add(proprietario)
    else:
        empresa.dinheiro += valor_lucro_empresa_dinheiro

    # 3. Imposto (Pago ao Governo/Região - Estatal)
    estatal = regiao.empresas.filter_by(tipo='estatal', produto='ouro').first() # Específico para ouro
    if estatal:
        estatal.dinheiro += valor_imposto_dinheiro
        db.session.add(estatal)

    descricao_acao = (
        f"⛏️ Gastou {energia_gasta} E extraindo ouro em {empresa.nome} - {regiao.nome}. Lucro líquido: {format_currency_python(dinheiro_liquido_jogador)} e {gold_liquido_jogador:.2f} Kg."
    )

    hist = HistoricoAcao(
        jogador_id=jogador.id,
        tipo_acao='MINERACAO',
        descricao=descricao_acao,
        dinheiro_delta=dinheiro_liquido_jogador,
        gold_delta=gold_liquido_jogador
    )
    db.session.add(hist)

    # O commit será feito na rota, após o serviço retornar

    return (True, descricao_acao, levelup)

def mine_iron_action(jogador: Jogador, empresa: Empresa, regiao: Regiao, energia_gasta: int):
    """
    Executa a lógica de negócio de minerar ferro.
    Retorna (sucesso: bool, mensagem: str, levelup: bool)
    """
    
    # --- 1. CALCULAR FATORES (Do Serviço) ---
    fatores = calculate_player_factors(jogador)
    desconto_energia = fatores['desconto_energia']
    multiplicador_xp_educacao = fatores['multiplicador_xp_educacao']

    # --- 2. APLICAÇÃO DOS BÔNUS/DESCONTOS ---
    energia_gasta_real = ceil(energia_gasta * (1.0 - desconto_energia))
    
    # --- CÁLCULO DE GANHO, ESGOTAMENTO E XP (Usando Config) ---
    bonus_regional = 1.0 + (regiao.indice_desenvolvimento / 10.0) 
    
    ferro_base = current_app.config['FERRO_POR_ENERGIA'] * energia_gasta
    ferro_obtido = ferro_base * bonus_regional
    
    xp_trabalho_ganho_final = current_app.config['XP_TRABALHO_POR_ENERGIA'] * energia_gasta
    xp_geral_ganho_base = current_app.config['XP_GERAL_POR_ENERGIA'] * energia_gasta
    xp_geral_ganho_final = xp_geral_ganho_base * multiplicador_xp_educacao

    # 1. ESGOOTAMENTO: Reduz a reserva regional
    esgotamento_total = current_app.config['ESGOTAMENTO_POR_ENERGIA'] * energia_gasta
    regiao.reserva_ferro = max(0.0, regiao.reserva_ferro - esgotamento_total) 

    # 2. REGISTRAR RECURSO NA MINA (À ESPERA DE TRANSPORTE)
    recurso_mina = RecursoNaMina.query.filter_by(
        jogador_id=jogador.id, 
        regiao_id=regiao.id,
        tipo_recurso='ferro'
    ).first()
    
    tempo_limite = current_app.config['RECURSO_NA_MINA_EXPIRACAO_MIN']
    
    if not recurso_mina:
        recurso_mina = RecursoNaMina(
            jogador_id=jogador.id, regiao_id=regiao.id, tipo_recurso='ferro', quantidade=0.0, 
            data_expiracao=datetime.utcnow() + timedelta(minutes=tempo_limite)
        )
        db.session.add(recurso_mina)
    else:
        # Reseta a data de expiração se já existia
        recurso_mina.data_expiracao = datetime.utcnow() + timedelta(minutes=tempo_limite)
        
    recurso_mina.quantidade += ferro_obtido # Adiciona o ferro obtido

    # 3. ATUALIZAÇÃO DO JOGADOR (Gasto e XP)
    jogador.energia -= energia_gasta_real # <- USA A ENERGIA REAL
    jogador.experiencia_trabalho += xp_trabalho_ganho_final
    jogador.experiencia += xp_geral_ganho_final
    
    levelup = jogador.check_level_up()

    # 4. REGISTRO NO HISTÓRICO
    descricao_acao = (
        f"⛏️ Gastou {energia_gasta} E extraindo ferro em {empresa.nome} - {regiao.nome}. Lucro: {ferro_obtido:.0f} toneladas."
    )
    hist = HistoricoAcao(
        jogador_id=jogador.id, tipo_acao='MINERACAO',
        descricao=descricao_acao, dinheiro_delta=0.0, gold_delta=0.0
    )
    
    db.session.add_all([recurso_mina, hist])
    
    return (True, descricao_acao, levelup)