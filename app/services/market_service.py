from app import db
from app.models import Jogador, Regiao, ArmazemRecurso, MarketOrder, RecursoNaMina, HistoricoAcao
from app.services.player_service import calculate_player_factors
from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy import func

def _calculate_tax(creator_jogador: Jogador, order_regiao: Regiao, total_value: float):
    """
    Calcula o imposto que o CRIADOR da ordem deve pagar,
    com base na sua habilidade de Filantropia e na taxa da Região.
    """
    taxa_base_regional = order_regiao.taxa_imposto_geral
    
    # Pega o desconto de imposto do jogador (de 0.0 a 0.5)
    fatores = calculate_player_factors(creator_jogador)
    desconto_filantropia = fatores['desconto_imposto']
    
    taxa_efetiva = taxa_base_regional * (1.0 - desconto_filantropia)
    imposto_devido = total_value * taxa_efetiva
    
    return imposto_devido

# --- FUNÇÃO 1: CRIAR ORDEM DE VENDA ---
def create_sell_order(creator_jogador: Jogador, resource_type: str, quantity: float, price_per_unit: float):
    """
    Cria uma ordem de VENDA.
    Tranca os recursos no armazém do Vendedor (Creator).
    Retorna (True, "Mensagem") ou (False, "Erro")
    """
    if quantity <= 0 or price_per_unit <= 0:
        return (False, "Valores inválidos.")

    # 1. Encontrar o recurso no armazém
    recurso_armazem = creator_jogador.armazem.recursos.filter_by(tipo=resource_type).first()
    
    if not recurso_armazem:
        return (False, "Recurso não encontrado no seu armazém.")
        
    # 2. Verificar se tem recurso disponível (não reservado)
    available_quantity = recurso_armazem.quantidade - recurso_armazem.quantidade_reservada
    
    if available_quantity < quantity:
        return (False, f"Recursos insuficientes. Você tem {available_quantity:.0f}t disponíveis para vender.")
        
    try:
        # 3. Trancar (Escrow) o recurso
        recurso_armazem.quantidade_reservada += quantity
        
        # 4. Criar a Ordem
        duration_hours = current_app.config['MARKET_ORDER_DURATION_HOURS']
        data_expiracao = datetime.utcnow() + timedelta(hours=duration_hours)
        
        nova_ordem = MarketOrder(
            jogador_id=creator_jogador.id,
            regiao_id=creator_jogador.regiao_atual_id, # Imposto será baseado na região do vendedor
            order_type='SELL',
            resource_type=resource_type,
            quantity=quantity,
            quantity_remaining=quantity,
            price_per_unit=price_per_unit,
            data_expiracao=data_expiracao,
            status='ACTIVE'
        )
        
        db.session.add(recurso_armazem)
        db.session.add(nova_ordem)
        # O commit será feito na rota
        
        return (True, f"Ordem de venda de {quantity:.0f}t de {resource_type} criada com sucesso.")

    except Exception as e:
        db.session.rollback()
        return (False, f"Erro ao criar ordem: {e}")

# --- FUNÇÃO 2: CRIAR ORDEM de COMPRA ---
def create_buy_order(creator_jogador: Jogador, resource_type: str, quantity: float, price_per_unit: float):
    """
    Cria uma ordem de COMPRA.
    Tranca o dinheiro na carteira do Comprador (Creator).
    Retorna (True, "Mensagem") ou (False, "Erro")
    """
    if quantity <= 0 or price_per_unit <= 0:
        return (False, "Valores inválidos.")

    total_cost = quantity * price_per_unit 
    order_regiao = db.session.get(Regiao, creator_jogador.regiao_atual_id)
    imposto_devido = _calculate_tax(creator_jogador, order_regiao, total_cost)
    custo_total_com_imposto = total_cost + imposto_devido
    
    # 1. Verificar se tem dinheiro disponível (não reservado)
    available_money = creator_jogador.dinheiro - creator_jogador.dinheiro_reservado
    
    if available_money < custo_total_com_imposto:
        return (False, f"Dinheiro insuficiente. Você precisa de R$ {custo_total_com_imposto:,.2f} (R$ {total_cost:,.2f} + R$ {imposto_devido:,.2f} de imposto) e tem R$ {available_money:,.2f} disponíveis.")
        
    try:
        # 2. Trancar (Escrow) o dinheiro
        creator_jogador.dinheiro_reservado += custo_total_com_imposto
        
        # 3. Criar a Ordem
        duration_hours = current_app.config['MARKET_ORDER_DURATION_HOURS']
        data_expiracao = datetime.utcnow() + timedelta(hours=duration_hours)
        
        nova_ordem = MarketOrder(
            jogador_id=creator_jogador.id,
            regiao_id=creator_jogador.regiao_atual_id, # Imposto será baseado na região do comprador
            order_type='BUY',
            resource_type=resource_type,
            quantity=quantity,
            quantity_remaining=quantity,
            price_per_unit=price_per_unit,
            data_expiracao=data_expiracao,
            status='ACTIVE'
        )
        
        db.session.add(creator_jogador)
        db.session.add(nova_ordem)
        # O commit será feito na rota
        
        return (True, f"Ordem de compra de {quantity:.0f}t de {resource_type} criada com sucesso.")

    except Exception as e:
        db.session.rollback()
        return (False, f"Erro ao criar ordem: {e}")

# --- FUNÇÃO 3: PREENCHER/TOMAR ORDEM ---
def fill_order(taker_jogador: Jogador, order_id: int, quantity_to_fill: float):
    """
    Executa a transação (Compra ou Venda) de uma ordem existente.
    Esta é a lógica mais complexa.
    Retorna (True, "Mensagem") ou (False, "Erro")
    """
    
    # 1. Validação inicial da Ordem
    order = db.session.get(MarketOrder, order_id)
    
    if not order or order.status != 'ACTIVE':
        return (False, "Esta ordem não está mais ativa.")
        
    if order.jogador_id == taker_jogador.id:
        return (False, "Você não pode negociar com você mesmo.")
        
    # 2. Validar e ajustar quantidade
    if quantity_to_fill <= 0:
        return (False, "Quantidade inválida.")
    
    # Garante que o jogador não tente pegar mais do que o disponível na ordem
    quantity_to_fill = min(quantity_to_fill, order.quantity_remaining)
    
    creator_jogador = db.session.get(Jogador, order.jogador_id)
    order_regiao = db.session.get(Regiao, order.regiao_id)
    
    # Custo bruto da transação
    total_value = quantity_to_fill * order.price_per_unit
    
    # --- LÓGICA DE TRANSAÇÃO ---
    # Usamos um try/except para garantir que a transação inteira funcione ou falhe
    try:
        
        if order.order_type == 'SELL':
            # === CASO A: TAKER (Comprador) está COMPRANDO de uma ordem 'SELL' ===
            # Creator = Vendedor (Paga imposto)
            # Taker = Comprador (Paga logística, paga R$)
            
            # 1. Taker (Comprador) tem dinheiro?
            if taker_jogador.dinheiro < total_value:
                return (False, "Dinheiro insuficiente para esta compra.")
                
            # 2. Calcular Imposto (Pago pelo Creator/Vendedor)
            imposto_devido = _calculate_tax(creator_jogador, order_regiao, total_value)
            lucro_liquido_creator = total_value - imposto_devido
            
            # 3. Transação Financeira
            taker_jogador.dinheiro -= total_value
            creator_jogador.dinheiro += lucro_liquido_creator
            
            # 4. Transação de Itens (Liberar do Escrow do Vendedor)
            recurso_creator = creator_jogador.armazem.recursos.filter_by(tipo=order.resource_type).first()
            if not recurso_creator or recurso_creator.quantidade_reservada < quantity_to_fill:
                 raise Exception("Erro crítico de Escrow do Vendedor.") # Falha de segurança, reverte
                 
            recurso_creator.quantidade_reservada -= quantity_to_fill
            recurso_creator.quantidade -= quantity_to_fill # Remove o item permanentemente
            
            # 5. Logística (Taker/Comprador resolve)
            # Criamos o recurso na mina da *região da ordem* para o *Taker* buscar
            recurso_na_mina = RecursoNaMina(
                jogador_id=taker_jogador.id,
                regiao_id=order.regiao_id,
                tipo_recurso=order.resource_type,
                quantidade=quantity_to_fill,
                data_expiracao = datetime.utcnow() + timedelta(minutes=current_app.config['RECURSO_NA_MINA_EXPIRACAO_MIN'])
            )
            db.session.add(recurso_na_mina)
            
            # 6. Atualizar Ordem
            order.quantity_remaining -= quantity_to_fill
            if order.quantity_remaining <= 0.001: # Evitar problemas de float
                order.status = 'COMPLETED'

            # 7. Histórico
            db.session.add(HistoricoAcao(jogador_id=creator_jogador.id, tipo_acao='VENDA_MERCADO', descricao=f"Vendeu {quantity_to_fill:.0f}t de {order.resource_type} por R$ {total_value:,.2f} (Líquido: R$ {lucro_liquido_creator:,.2f})", dinheiro_delta=lucro_liquido_creator))
            db.session.add(HistoricoAcao(jogador_id=taker_jogador.id, tipo_acao='COMPRA_MERCADO', descricao=f"Comprou {quantity_to_fill:.0f}t de {order.resource_type} por R$ {total_value:,.2f}. Recurso em {order_regiao.nome}.", dinheiro_delta=-total_value))
            
            return (True, f"Compra de {quantity_to_fill:.0f}t realizada! O recurso está em {order_regiao.nome} aguardando seu transporte.")

        elif order.order_type == 'BUY':
            # === CASO B: TAKER (Vendedor) está VENDENDO para uma ordem 'BUY' ===
            # Creator = Comprador (Paga imposto, paga R$)
            # Taker = Vendedor (Paga logística, recebe R$)
            
            # 1. Taker (Vendedor) tem o recurso?
            recurso_taker = taker_jogador.armazem.recursos.filter_by(tipo=order.resource_type).first()
            available_quantity = 0
            if recurso_taker:
                available_quantity = recurso_taker.quantidade - recurso_taker.quantidade_reservada
            
            if available_quantity < quantity_to_fill:
                return (False, f"Você não tem {quantity_to_fill:.0f}t de {order.resource_type} disponíveis para vender.")

            # 2. Calcular Imposto (Pago pelo Creator/Comprador)
            imposto_devido = _calculate_tax(creator_jogador, order_regiao, total_value)

            custo_total_com_imposto = total_value + imposto_devido
            
            creator_jogador.dinheiro_reservado -= custo_total_com_imposto
            creator_jogador.dinheiro -= imposto_devido # Paga o imposto
            taker_jogador.dinheiro += total_value
            
            # 5. Transação de Itens
            recurso_taker.quantidade -= quantity_to_fill
            
            # 6. Logística (Taker/Vendedor resolve)
            # Criamos o recurso na mina da *região do Taker* para o *Creator* buscar
            recurso_na_mina = RecursoNaMina(
                jogador_id=creator_jogador.id,
                regiao_id=taker_jogador.regiao_atual_id, # Região do VENDEDOR
                tipo_recurso=order.resource_type,
                quantidade=quantity_to_fill,
                data_expiracao = datetime.utcnow() + timedelta(minutes=current_app.config['RECURSO_NA_MINA_EXPIRACAO_MIN'])
            )
            db.session.add(recurso_na_mina)
            
            # 7. Atualizar Ordem
            order.quantity_remaining -= quantity_to_fill
            if order.quantity_remaining <= 0.001:
                order.status = 'COMPLETED'
                
            # 8. Histórico
            db.session.add(HistoricoAcao(jogador_id=creator_jogador.id, tipo_acao='COMPRA_MERCADO', descricao=f"Comprou {quantity_to_fill:.0f}t de {order.resource_type} por R$ {total_value:,.2f} (Imposto: R$ {imposto_devido:,.2f}). Recurso em {taker_jogador.regiao_atual.nome}.", 
                                         dinheiro_delta=0,
                                         gold_delta=0))
            db.session.add(HistoricoAcao(jogador_id=taker_jogador.id, tipo_acao='VENDA_MERCADO', descricao=f"Vendeu {quantity_to_fill:.0f}t de {order.resource_type} por R$ {total_value:,.2f} para uma ordem de compra.", dinheiro_delta=total_value))

            return (True, f"Venda de {quantity_to_fill:.0f}t realizada com sucesso!")

    except Exception as e:
        db.session.rollback()
        return (False, f"Erro ao processar transação: {e}")

# --- FUNÇÃO 4: CANCELAR ORDEM ---
def cancel_order(jogador: Jogador, order_id: int):
    """
    Cancela uma ordem ATIVA que pertence ao jogador.
    Devolve o Escrow (dinheiro ou itens).
    """
    order = db.session.get(MarketOrder, order_id)

    if not order:
        return (False, "Ordem não encontrada.")
    if order.jogador_id != jogador.id:
        return (False, "Você não é o dono desta ordem.")
    if order.status != 'ACTIVE':
        return (False, "A ordem não está mais ativa.")
        
    try:
        order.status = 'CANCELLED'
        
        # Devolver o Escrow
        if order.order_type == 'SELL':
            # Devolve itens reservados
            recurso = jogador.armazem.recursos.filter_by(tipo=order.resource_type).first()
            if recurso:
                recurso.quantidade_reservada = max(0, recurso.quantidade_reservada - order.quantity_remaining)
                db.session.add(recurso)
                
        elif order.order_type == 'BUY':
            # 1. Calcula o valor restante
            custo_valor_restante = order.quantity_remaining * order.price_per_unit
            
            # 2. Calcula o imposto restante (com base no valor restante)
            imposto_restante = _calculate_tax(jogador, order.regiao, custo_valor_restante)
            
            # 3. Devolve a soma
            total_a_devolver = custo_valor_restante + imposto_restante
            
            jogador.dinheiro_reservado = max(0, jogador.dinheiro_reservado - total_a_devolver)
            db.session.add(jogador)
            
        db.session.add(order)
        return (True, "Ordem cancelada e recursos/dinheiro devolvidos.")
        
    except Exception as e:
        db.session.rollback()
        return (False, f"Erro ao cancelar ordem: {e}")
    