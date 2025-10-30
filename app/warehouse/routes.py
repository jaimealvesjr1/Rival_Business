from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.warehouse import bp
from app import db
from app.models import Jogador, Veiculo, ArmazemRecurso, TipoVeiculo, Armazem, TreinamentoAtivo, TransporteAtivo, HistoricoAcao, RecursoNaMina
from datetime import datetime, timedelta
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

@bp.route('/')
@login_required
def view_warehouse():
    jogador = Jogador.query.get(current_user.id)
    armazem = jogador.armazem 
    
    # Se o armazém não existir (A lógica de run.py deve garantir que não seja None)
    if not armazem:
        flash("Erro crítico: Armazém não inicializado.", 'danger')
        return redirect(url_for('profile.view_profile'))
        
    # Carregar dados para o template
    recursos_armazem = ArmazemRecurso.query.filter_by(armazem_id=armazem.id).all()
    frota = armazem.frota.all()
    peso_atual = sum(r.quantidade for r in recursos_armazem)
    modelos_veiculos = TipoVeiculo.query.order_by(TipoVeiculo.nivel_especializacao_req).all()
    
    # --- CONSOLIDAÇÃO DA LÓGICA DE UPGRADE NO BACKEND ---
    upgrade_list_data = [
        {'display_name': 'Capacidade', 'type': 'capacidade', 'info': armazem.get_capacidade_upgrade_info(), 'current_level': armazem.nivel_capacidade},
        {'display_name': 'Frota', 'type': 'frota', 'info': armazem.get_frota_upgrade_info(), 'current_level': armazem.nivel_frota},
        {'display_name': 'Especialização', 'type': 'especializacao', 'info': armazem.get_especializacao_upgrade_info(), 'current_level': armazem.nivel_especializacao},
    ]
    
    # Variável de Status de Treino (para o template)
    treino_ativo = jogador.treino_ativo 
    
    ultima_viagem = TransporteAtivo.query.filter_by(
        jogador_id=jogador.id
    ).order_by(TransporteAtivo.data_fim.desc()).first()
    
    tempo_total_restante = 0
    if ultima_viagem:
        tempo_restante_dt = ultima_viagem.data_fim - datetime.utcnow()
        if tempo_restante_dt.total_seconds() > 0:
            tempo_total_restante = int(tempo_restante_dt.total_seconds())

    # 1. Carregar Recursos na Mina (aguardando frete)
    recursos_mina = RecursoNaMina.query.filter_by(jogador_id=jogador.id).all()
    recursos_por_regiao = {}

    for recurso in recursos_mina:
        tempo_restante_exp = (recurso.data_expiracao - datetime.utcnow()).total_seconds()
        recurso.tempo_restante_exp = max(0, int(tempo_restante_exp))
        
        if recurso.regiao_id not in recursos_por_regiao:
            recursos_por_regiao[recurso.regiao_id] = {'regiao_nome': recurso.regiao.nome, 'recursos': []}
        recursos_por_regiao[recurso.regiao_id]['recursos'].append(recurso)
    
    # 2. Carregar Frota Disponível
    frota_completa = armazem.frota.all()
    # Veículos que não estão em nenhuma Viagem Ativa
    veiculos_disponiveis = [v for v in frota_completa if not v.transporte_atual]

    transporte_ativo_total = TransporteAtivo.query.filter_by(jogador_id=jogador.id).all()
    
    # Soma a quantidade de recursos em todas essas viagens
    # O filtro sum é mais robusto para listas vazias, mas um loop simples garante o float.
    recurso_em_transito = sum(t.quantidade for t in transporte_ativo_total)
    # ----------------------------------------------------------------------
    
    return render_template('warehouse/view_warehouse.html',
                           title=f"Armazém de {jogador.username}",
                           jogador=jogador,
                           armazem=armazem,
                           recursos_armazem=recursos_armazem,
                           frota=frota,
                           peso_atual=peso_atual,
                           upgrade_list=upgrade_list_data,
                           treino_ativo=treino_ativo,
                           modelos_veiculos=modelos_veiculos,
                           tempo_total_restante=tempo_total_restante,
                           ultima_viagem=ultima_viagem,
                           recurso_em_transito=recurso_em_transito, 
                           recursos_por_regiao=recursos_por_regiao,
                           veiculos_disponiveis=veiculos_disponiveis, **footer)

@bp.route('/upgrade/<string:type>', methods=['POST'])
@login_required
def start_upgrade(type):
    jogador = Jogador.query.get(current_user.id)
    armazem = jogador.armazem
    
    # 1. MAPEAR O TIPO E DEFINIR MÉTODOS
    upgrade_map = {
        'capacidade': {'info_method': armazem.get_capacidade_upgrade_info, 'attr': 'nivel_capacidade'},
        'frota':      {'info_method': armazem.get_frota_upgrade_info, 'attr': 'nivel_frota'},
        'especializacao': {'info_method': armazem.get_especializacao_upgrade_info, 'attr': 'nivel_especializacao'}
    }

    upgrade_data = upgrade_map.get(type) # Usa um nome mais descritivo
    
    # 2. VERIFICAÇÃO DE VALIDADE DO TIPO
    if not upgrade_data:
        flash("Tipo de melhoria inválido.", 'danger')
        return redirect(url_for('warehouse.view_warehouse'))
        
    # 3. CALCULAR INFORMAÇÕES E NÍVEL ATUAL (USANDO O MAPA)
    info = upgrade_data['info_method']() # Chama o método correto: info_method()
    nivel_atual = getattr(armazem, upgrade_data['attr']) # Obtém o nível atual (e.g., armazem.nivel_frota)

    if jogador.treino_ativo and jogador.treino_ativo.habilidade.startswith('armazem_') and jogador.treino_ativo.habilidade != f'armazem_{type}':
        flash("Você já está melhorando outro aspecto do Armazém. Apenas uma melhoria de Armazém por vez.", 'warning')
        return redirect(url_for('warehouse.view_warehouse'))

    # 5. VERIFICAÇÃO DE CUSTOS
    if jogador.dinheiro < info['money'] or jogador.gold < info['gold']:
        flash(f"Fundos insuficientes. Requer R${info['money']:.0f} e G{info['gold']:.0f}.", 'danger')
        return redirect(url_for('warehouse.view_warehouse'))
        
    try:
        # 6. SUBTRAIR CUSTO E INICIAR TREINO DO ARMAZÉM
        jogador.dinheiro -= info['money']
        jogador.gold -= info['gold']
        
        data_fim = datetime.utcnow() + timedelta(minutes=info['time'])
        
        # Usamos o modelo TreinamentoAtivo, com o nome correto
        treino = TreinamentoAtivo(
            jogador_id=jogador.id,
            habilidade=f'armazem_{type}', # e.g., 'armazem_frota'
            nivel_alvo=nivel_atual + 1, 
            data_fim=data_fim
        )
        
        db.session.add(treino)
        db.session.commit()
        
        flash(f"Melhoria de {type.capitalize()} iniciada! Conclusão em {info['time']} minutos.", 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao iniciar melhoria: {e}", 'danger')
        
    return redirect(url_for('warehouse.view_warehouse'))

@bp.route('/buy_vehicle/<string:tipo_veiculo>', methods=['POST'])
@login_required
def buy_vehicle(tipo_veiculo):
    jogador = Jogador.query.get(current_user.id)
    armazem = jogador.armazem
    tipo_modelo = TipoVeiculo.query.filter_by(tipo_veiculo=tipo_veiculo).first()
    
    if not tipo_modelo:
        flash("Modelo de veículo inválido.", 'danger')
        return redirect(url_for('warehouse.view_warehouse'))

    # 1. VERIFICAÇÃO DE LIMITE DE FROTA
    if len(armazem.frota.all()) >= armazem.get_max_frota():
        flash("Limite de frota atingido. Aumente o nível de Frota do seu Armazém.", 'danger')
        return redirect(url_for('warehouse.view_warehouse'))

    # 2. VERIFICAÇÃO DE REQUISITOS (Nível Especialização do Armazém)
    if armazem.nivel_especializacao < tipo_modelo.nivel_especializacao_req:
        flash(f"Nível de Especialização ({armazem.nivel_especializacao}) insuficiente para comprar este veículo.", 'danger')
        return redirect(url_for('warehouse.view_warehouse'))

    # 3. VERIFICAÇÃO DE CUSTOS (Dinheiro, Gold, Ferro)
    ferro_atual = armazem.recursos.filter_by(tipo='ferro').first()
    ferro_qtd = ferro_atual.quantidade if ferro_atual else 0
    
    if (jogador.dinheiro < tipo_modelo.custo_money or 
        jogador.gold < tipo_modelo.custo_gold or 
        ferro_qtd < tipo_modelo.custo_ferro):
        
        msg = f"Fundos insuficientes. Requer R${tipo_modelo.custo_money}, G{tipo_modelo.custo_gold} e {tipo_modelo.custo_ferro} Ferro."
        flash(msg, 'danger')
        return redirect(url_for('warehouse.view_warehouse'))

    try:
        # 4. AÇÃO: Subtrair custos e criar veículo
        jogador.dinheiro -= tipo_modelo.custo_money
        jogador.gold -= tipo_modelo.custo_gold
        ferro_atual.quantidade -= tipo_modelo.custo_ferro # Subtrai Ferro do armazém

        novo_veiculo = Veiculo(
            armazem_id=armazem.id,
            nome=tipo_modelo.nome_display,
            tipo_veiculo=tipo_modelo.tipo_veiculo,
            capacidade=tipo_modelo.capacidade,
            velocidade=tipo_modelo.velocidade,
            custo_tonelada_km=tipo_modelo.custo_tonelada_km,
            validade_dias=tipo_modelo.validade_dias,
            nivel_especializacao_req=tipo_modelo.nivel_especializacao_req
        )

        # --- REGISTRO NO HISTÓRICO ---
        descricao_acao = (
            f"Compra de {novo_veiculo.nome}. Custo: R${tipo_modelo.custo_money} e G{tipo_modelo.custo_gold} e {tipo_modelo.custo_ferro} Ferro."
        )
        hist = HistoricoAcao(
            jogador_id=jogador.id,
            tipo_acao='VEICULO_COMPRA',
            descricao=descricao_acao,
            dinheiro_delta=-tipo_modelo.custo_money, 
            gold_delta=-tipo_modelo.custo_gold
        )
        db.session.add_all([hist, novo_veiculo])

        db.session.commit()
        
        flash(f"Veículo '{novo_veiculo.nome}' adicionado à frota!", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao comprar veículo: {e}", 'danger')
        
    return redirect(url_for('warehouse.view_warehouse'))