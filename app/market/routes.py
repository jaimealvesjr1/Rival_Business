from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.market import bp
from app.models import Jogador, PrecoMercado, ArmazemRecurso, HistoricoAcao
from app.utils import format_currency_python
from config import Config
from math import floor

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

# ------------------------------------------------------------------
# ROTA PRINCIPAL: VISUALIZAÇÃO DO MERCADO
# ------------------------------------------------------------------
@bp.route('/')
@login_required
def view_market():
    jogador = Jogador.query.get(current_user.id)
    
    # Obter preços e recursos
    precos = PrecoMercado.query.all()
    recursos_armazem = {r.tipo: r for r in jogador.armazem.recursos.all()}

    return render_template('market/view_market.html',
                           title='Mercado Global',
                           jogador=jogador,
                           precos=precos,
                           recursos_armazem=recursos_armazem, **footer)

# ------------------------------------------------------------------
# ROTA DE AÇÃO: COMPRA/VENDA (Exemplo: Vender Minério de Ferro)
# ------------------------------------------------------------------
@bp.route('/sell/<string:recurso_tipo>', methods=['POST'])
@login_required
def sell_resource(recurso_tipo):
    jogador = Jogador.query.get(current_user.id)
    
    # Obter dados do formulário
    quantidade = request.form.get('quantidade', type=float)
    if not quantidade or quantidade <= 0:
        flash("Quantidade inválida.", 'danger')
        return redirect(url_for('market.view_market'))
        
    preco_info = PrecoMercado.query.filter_by(tipo_recurso=recurso_tipo).first()
    recurso_armazem = jogador.armazem.recursos.filter_by(tipo=recurso_tipo).first()
    
    if not preco_info or not recurso_armazem or recurso_armazem.quantidade < quantidade:
        flash(f"Recurso '{recurso_tipo.capitalize()}' não encontrado ou saldo insuficiente.", 'danger')
        return redirect(url_for('market.view_market'))
        
    try:
        # 1. Cálculo do Ganho e Atualização do Armazém
        ganho_total = quantidade * preco_info.preco_venda_dinheiro
        jogador.dinheiro += ganho_total
        recurso_armazem.quantidade -= quantidade
        
        # 2. Histórico
        descricao = f"Vendeu {quantidade:.0f}t de {recurso_tipo.capitalize()} por {format_currency_python(ganho_total)}."
        hist = HistoricoAcao(
            jogador_id=jogador.id, tipo_acao='VENDA_RECURSO',
            descricao=descricao, dinheiro_delta=ganho_total, gold_delta=0.0
        )
        
        db.session.add_all([jogador, recurso_armazem, hist])
        db.session.commit()
        
        flash(f"Venda concluída! Ganhou {format_currency_python(ganho_total)}.", 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao vender recurso: {e}", 'danger')
        
    return redirect(url_for('market.view_market'))
