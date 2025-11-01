from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.market import bp
from app.models import Jogador, MarketOrder
from app.market.forms import MarketOrderForm
from app.services import market_service
from config import Config
from sqlalchemy import or_

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

@bp.route('/', methods=['GET', 'POST'])
@login_required
def view_market():
    jogador = Jogador.query.get(current_user.id)
    form = MarketOrderForm()

    # --- Lógica de CRIAR ORDEM (POST) ---
    if form.validate_on_submit():
        # Verifica qual botão foi pressionado
        try:
            if form.submit_sell.data:
                # --- Criar Ordem de VENDA ---
                success, message = market_service.create_sell_order(
                    creator_jogador=jogador,
                    resource_type=form.resource_type.data,
                    quantity=form.quantity.data,
                    price_per_unit=form.price_per_unit.data
                )
            elif form.submit_buy.data:
                # --- Criar Ordem de COMPRA ---
                success, message = market_service.create_buy_order(
                    creator_jogador=jogador,
                    resource_type=form.resource_type.data,
                    quantity=form.quantity.data,
                    price_per_unit=form.price_per_unit.data
                )
            else:
                success = False
                message = "Ação de formulário inválida."

            if success:
                db.session.commit()
                flash(message, 'success')
            else:
                db.session.rollback() # Desfaz o escrow se o serviço falhou
                flash(message, 'danger')
                
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao processar ordem: {e}", 'danger')
            
        return redirect(url_for('market.view_market'))

    # --- Lógica de MOSTRAR MERCADO (GET) ---
    
    # 1. Ordens de Venda (As mais baratas primeiro)
    sell_orders = MarketOrder.query.filter(
        MarketOrder.order_type == 'SELL',
        MarketOrder.status == 'ACTIVE',
        MarketOrder.jogador_id != jogador.id # Não mostrar suas próprias ordens de venda
    ).order_by(MarketOrder.price_per_unit.asc()).all()

    # 2. Ordens de Compra (As mais caras primeiro)
    buy_orders = MarketOrder.query.filter(
        MarketOrder.order_type == 'BUY',
        MarketOrder.status == 'ACTIVE',
        MarketOrder.jogador_id != jogador.id # Não mostrar suas próprias ordens de compra
    ).order_by(MarketOrder.price_per_unit.desc()).all()

    # 3. Minhas Ordens Ativas
    my_active_orders = MarketOrder.query.filter(
        MarketOrder.jogador_id == jogador.id,
        MarketOrder.status == 'ACTIVE'
    ).order_by(MarketOrder.data_criacao.desc()).all()
    
    # 4. Saldo Disponível (calculando o que está reservado)
    recursos_armazem = {r.tipo: (r.quantidade - r.quantidade_reservada) for r in jogador.armazem.recursos.all()}
    dinheiro_disponivel = jogador.dinheiro - jogador.dinheiro_reservado

    return render_template('market/view_market.html',
                           title='Mercado P2P',
                           jogador=jogador,
                           form=form,
                           sell_orders=sell_orders,
                           buy_orders=buy_orders,
                           my_active_orders=my_active_orders,
                           recursos_armazem=recursos_armazem,
                           dinheiro_disponivel=dinheiro_disponivel,
                           **footer)

@bp.route('/fill/<int:order_id>', methods=['POST'])
@login_required
def fill_order(order_id):
    jogador = Jogador.query.get(current_user.id)
    
    try:
        # A quantidade vem do formulário da tabela
        quantity_to_fill = request.form.get('quantity', type=float)
        if not quantity_to_fill or quantity_to_fill <= 0:
            flash("Quantidade para negociar inválida.", 'danger')
            return redirect(url_for('market.view_market'))
            
        success, message = market_service.fill_order(
            taker_jogador=jogador,
            order_id=order_id,
            quantity_to_fill=quantity_to_fill
        )
        
        if success:
            db.session.commit()
            flash(message, 'success')
        else:
            db.session.rollback()
            flash(message, 'danger')
            
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar transação: {e}", 'danger')

    return redirect(url_for('market.view_market'))

@bp.route('/cancel/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    jogador = Jogador.query.get(current_user.id)
    
    try:
        success, message = market_service.cancel_order(
            jogador=jogador,
            order_id=order_id
        )
        
        if success:
            db.session.commit()
            flash(message, 'success')
        else:
            db.session.rollback()
            flash(message, 'danger')
            
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao cancelar ordem: {e}", 'danger')

    return redirect(url_for('market.view_market'))
