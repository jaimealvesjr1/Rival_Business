from app import db
from app.models import Jogador, Empresa, ArmazemRecurso, ProductionRecipe, ProductionJob, HistoricoAcao
from app.services.player_service import calculate_player_factors
from datetime import datetime, timedelta
from flask import current_app
from math import ceil

def start_manufacturing(jogador: Jogador, empresa: Empresa, recipe_id: int, cycles: int) -> tuple:
    """
    Inicia uma nova produção na empresa do jogador.
    Retorna (True, "Mensagem") ou (False, "Erro")
    """
    
    # 1. Validações e Busca de Receita
    recipe = ProductionRecipe.query.get(recipe_id)
    if not recipe:
        return (False, "Receita de produção inválida.")
        
    if empresa.tipo_producao != recipe.factory_type:
        return (False, f"Esta empresa ({empresa.nome}) não é do tipo certo ({recipe.factory_type}) para esta receita.")

    if cycles <= 0:
        return (False, "Número de ciclos inválido.")
        
    # 2. Pré-requisitos de Custo e Tempo
    total_energy_cost = recipe.energy_cost * cycles
    total_input_quantity = recipe.input_quantity * cycles
    
    # 2.1 Custo de Energia (com bônus de Saúde)
    fatores = calculate_player_factors(jogador)
    desconto_energia = fatores['desconto_energia']
    real_energy_cost = ceil(total_energy_cost * (1.0 - desconto_energia))
    
    if jogador.energia < real_energy_cost:
        return (False, f"Energia insuficiente. Você precisa de {real_energy_cost} E (Base: {total_energy_cost} E).")

    # 2.2 Requisito de Item de Entrada (Tirado do Armazém)
    # Nota: Assumimos que o ArmazemRecurso existe. Se não existir, a quantidade é 0.
    armazem_recurso = jogador.armazem.recursos.filter_by(tipo=recipe.input_item_type).first()
    
    if not armazem_recurso or armazem_recurso.quantidade < total_input_quantity:
        return (False, f"Recursos de entrada insuficientes: Você precisa de {total_input_quantity:.0f}t de {recipe.input_item_type}.")

    # 3. Cálculo de Tempo de Conclusão
    total_time_minutes = recipe.production_time_minutes * cycles
    data_fim = datetime.utcnow() + timedelta(minutes=total_time_minutes)

    try:
        # 4. Iniciar Produção: Cobrar custos e criar Job
        
        # 4.1 Subtrair recursos e energia
        jogador.energia -= real_energy_cost
        armazem_recurso.quantidade -= total_input_quantity
        
        # 4.2 Criar o Job
        production_job = ProductionJob(
            jogador_id=jogador.id,
            empresa_id=empresa.id,
            recipe_id=recipe.id,
            quantity_multiplier=cycles,
            data_fim=data_fim
        )
        
        # 4.3 Registrar histórico
        descricao_acao = (
            f"🏭 Iniciou produção de {recipe.output_item_type} ({cycles} ciclos). Custo: {total_input_quantity:.0f}t {recipe.input_item_type} e {real_energy_cost} E."
        )
        hist = HistoricoAcao(
            jogador_id=jogador.id,
            tipo_acao='PRODUCAO_INICIO',
            descricao=descricao_acao,
            dinheiro_delta=0.0,
            gold_delta=0.0
        )

        db.session.add_all([production_job, armazem_recurso, jogador, hist])
        
        return (True, f"Produção de {recipe.output_item_type.capitalize()} iniciada ({cycles} ciclos). Conclusão em {total_time_minutes} minutos.")

    except Exception as e:
        db.session.rollback()
        return (False, f"Erro ao iniciar produção: {e}")

def complete_manufacturing_jobs(job: ProductionJob, jogador: Jogador):
    """
    Finaliza o job de produção, credita os itens no Armazém.
    """
    recipe = job.recipe
    
    # 1. Calcular a saída final
    output_quantity = recipe.output_quantity * job.quantity_multiplier
    output_item_type = recipe.output_item_type

    # 2. Creditar no Armazém do Jogador
    armazem_recurso = jogador.armazem.recursos.filter_by(tipo=output_item_type).first()
    if not armazem_recurso:
        from app.models import ArmazemRecurso
        armazem_recurso = ArmazemRecurso(armazem_id=jogador.armazem.id, tipo=output_item_type, quantidade=0.0)
        db.session.add(armazem_recurso)
        
    armazem_recurso.quantidade += output_quantity

    # 3. Registrar Histórico
    descricao_acao = (
        f"✅ Produção concluída: {output_quantity:.0f}t de {output_item_type.capitalize()} (Receita: {recipe.name})."
    )
    hist = HistoricoAcao(
        jogador_id=jogador.id,
        tipo_acao='PRODUCAO_FIM',
        descricao=descricao_acao,
        dinheiro_delta=0.0, 
        gold_delta=0.0
    )
    
    # 4. Atualizar XP de Trabalho
    # Configuração Padrão: 50 XP por Ciclo
    xp_ganho = job.quantity_multiplier * current_app.config.get('XP_MANUFATURA_POR_CICLO', 50.0)
    jogador.experiencia_trabalho += xp_ganho
    
    db.session.add_all([armazem_recurso, jogador, hist])
    db.session.delete(job)
