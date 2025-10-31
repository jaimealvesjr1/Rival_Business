from flask import redirect, url_for, flash, request, render_template
from flask_login import login_required, current_user
from app import db
from app.utils import calculate_distance_km, format_currency_python
from app.models import Regiao, Jogador, ViagemAtiva, PedidoResidencia, Empresa, Armazem, ArmazemRecurso, HistoricoAcao, TransporteAtivo, Veiculo, RecursoNaMina
from app.game_actions import bp
from app.game_actions.forms import OpenCompanyForm
from datetime import datetime, timedelta
from math import ceil
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

XP_TRABALHO_POR_ENERGIA = 0.1       # XP Trabalho: 1 XP para 10 E (0.1 por E)
XP_GERAL_POR_ENERGIA = 10.0         # XP GERAL: 100 XP para 10 E (10.0 por E)
ESGOTAMENTO_POR_ENERGIA = 0.1       # Reserva: Esgota 0.1 unidade por 10 E

ENERGIA_MINERACAO = 10              # Gasto de energia
XP_TRABALHO_GANHA = 1.0
XP_GERAL_GANHA = 5.0                # XP geral é um bônus
GOLD_TO_MONEY_RATE = 1000.00        # 1 Gold = R$1.000
OURO_GANHO_FIXO = 15.0              # Ouro recebido pelo jogador, fixo por ação
XP_MAX_LEVEL = 115000               # XP máxima para o exemplo do cálculo.

OURO_POR_ENERGIA = 0.1              # Gold: 1 Gold para 10 E (0.1 por E)
FERRO_POR_ENERGIA = 1.5             # Ex: 15 ferro para 10 E (1.5 por E)

FATOR_REDUCAO_DINHEIRO = 0.1

TEMPO_BASE_ESPERA_MIN = 360
TEMPO_ESPERA_RESIDENCIA_HORAS = 6

VELOCIDADE_BASE_KMH = 100
HORA_POR_KM = 100 
CUSTO_POR_KM = 5.0
TEMPO_TRANSPORTE_LOCAL_MIN = 5
CUSTO_MINIMO_FRETE_LOCAL = 500
TEMPO_LIMITE_PLANEJAMENTO_MIN = 15

def get_money_production(xp_trabalho):
    """Calcula o valor total em dinheiro gerado pela ação, escalado pela XP."""    
    base_production = 50000 
    multiplicador = (1 + (xp_trabalho / XP_MAX_LEVEL) * 59.2) # Ajuste linear simplificado
    
    return base_production * multiplicador

def calculate_player_factors(jogador):
    """Calcula os fatores de bônus/desconto com base nas habilidades do jogador."""
    
    # SAÚDE: Desconto no Gasto de Energia (Max 80%)
    saude_level = jogador.habilidade_saude
    desconto_energia = min(0.80, saude_level * 0.01) 
    
    # EDUCAÇÃO: Bônus no Ganho de XP Geral (Max 80%)
    educacao_level = jogador.habilidade_educacao
    bonus_xp_geral = min(0.80, educacao_level * 0.01)
    
    # FILANTROPIA: Desconto no Imposto (Max 50%)
    filantropia_level = jogador.habilidade_filantropia
    desconto_imposto = min(0.50, filantropia_level * 0.01)
    
    return {
        'desconto_energia': desconto_energia,
        'multiplicador_xp_educacao': 1.0 + bonus_xp_geral,
        'desconto_imposto': desconto_imposto
    }

@bp.route('/travel', methods=['POST'])
@login_required
def travel():
    jogador = Jogador.query.get(current_user.id)
    regiao_atual = jogador.regiao_atual
    
    destino_id = request.form.get('destino_id', type=int)
    destino = Regiao.query.get(destino_id)

    if not destino or destino.id == regiao_atual.id:
        flash(format_currency_python("Destino inválido.", 'danger'))
        return redirect(url_for('map.view_map'))

    # 1. VERIFICAÇÃO CRÍTICA: Jogador já está viajando ou treinando?
    if ViagemAtiva.query.filter_by(jogador_id=jogador.id).first():
        flash("Você já está em viagem!", 'warning')
        return redirect(url_for('map.view_map'))
    
    try:
        # --- Lógica de Cálculo de Viagem (Tempo e Custo) ---
        HORA_POR_KM = 100 
        CUSTO_POR_KM = 5.0 
        
        aceleracao_percentual = jogador.regiao_atual.indice_desenvolvimento
        fator_aceleracao = 1.0 - (aceleracao_percentual / 100.0)
        
        distancia_bruta = calculate_distance_km(
            regiao_atual.latitude, regiao_atual.longitude, 
            destino.latitude, destino.longitude
        )

        distancia_efetiva = round(distancia_bruta * fator_aceleracao, 2)
        tempo_horas = ceil(distancia_efetiva / HORA_POR_KM)
        custo_total = round(distancia_efetiva * CUSTO_POR_KM, 2)
        
        # 2. VERIFICAÇÃO DE CUSTO
        if jogador.dinheiro < custo_total:
            flash(f"Dinheiro insuficiente. Você precisa de {format_currency_python(custo_total)}.", 'danger')
            return redirect(url_for('map.view_map'))

        # 3. AÇÃO: Subtrai dinheiro e inicia a Viagem
        jogador.dinheiro -= custo_total
        
        data_fim_viagem = datetime.utcnow() + timedelta(hours=tempo_horas)
        
        viagem = ViagemAtiva(
            jogador_id=jogador.id,
            destino_id=destino_id,
            data_fim=data_fim_viagem
        )
        
        db.session.add(viagem)
        db.session.commit()
        
        flash(f"Viagem iniciada para {destino.nome}! Duração: {tempo_horas} horas.", 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar viagem: {e}", 'danger')
        
    return redirect(url_for('map.view_map'))

@bp.route('/request_residency/<int:regiao_id>', methods=['POST'])
@login_required
def request_residency(regiao_id):
    jogador = Jogador.query.get(current_user.id)
    regiao_destino = Regiao.query.get(regiao_id)

    total_jogadores = Jogador.query.count()
    limite_maximo_residentes = ceil(total_jogadores * 0.50)
    residentes_atuais = regiao_destino.residentes.count()

    filantropia_regional = regiao_destino.indice_filantropia
    desconto_percentual = min(0.50, filantropia_regional)
    tempo_ajustado_min = TEMPO_BASE_ESPERA_MIN * (1.0 - desconto_percentual)
    
    # Verificação 1: Destino é válido e diferente da residência atual
    if not regiao_destino or regiao_destino.id == jogador.regiao_residencia_id:
        flash("Pedido inválido. Destino não pode ser sua residência atual.", 'danger')
        return redirect(url_for('map.view_map'))

    # Verificação 2: Já existe um pedido ativo
    if PedidoResidencia.query.filter_by(jogador_id=jogador.id).first():
        flash("Você já tem um pedido de residência ativo.", 'warning')
        return redirect(url_for('map.view_map'))
    
    if residentes_atuais >= limite_maximo_residentes:
        flash(f"O limite de residência para esta região ({limite_maximo_residentes}) foi atingido. Tente outra região.", 'danger')
        return redirect(url_for('profile.view_profile'))
        
    try:
        data_aprovacao = datetime.utcnow() + timedelta(minutes=tempo_ajustado_min)
        
        pedido = PedidoResidencia(
            jogador_id=jogador.id,
            regiao_destino_id=regiao_id,
            data_aprovacao=data_aprovacao
        )
        
        db.session.add(pedido)
        db.session.commit()
        flash(f"Pedido de residência em {regiao_destino.nome} enviado! Aprovação em 6 horas.", 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao solicitar residência: {e}", 'danger')
        
    return redirect(url_for('map.view_map'))

@bp.route('/cancel_residency', methods=['POST'])
@login_required
def cancel_residency():
    jogador = Jogador.query.get(current_user.id)
    pedido_ativo = PedidoResidencia.query.filter_by(jogador_id=jogador.id).first()
    
    if not pedido_ativo:
        flash("Você não tem um pedido de residência ativo para cancelar.", 'warning')
        return redirect(url_for('map.view_map'))
        
    try:
        regiao_destino_nome = Regiao.query.get(pedido_ativo.regiao_destino_id).nome
        db.session.delete(pedido_ativo)
        db.session.commit()
        flash(f"Pedido de residência em {regiao_destino_nome} cancelado com sucesso.", 'info')
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao cancelar pedido: {e}", 'danger')
        
    return redirect(url_for('map.view_map'))

@bp.route('/company/open', methods=['GET', 'POST']) 
@login_required
def open_company_view():
    jogador = Jogador.query.get(current_user.id)
    regiao = jogador.regiao_residencia 
    form = OpenCompanyForm()
    
    # Obter os custos (necessário para a visualização e validação)
    custos = jogador.get_open_company_cost()
    custo_gold = custos['gold']
    custo_money = custos['money']
    
    # --- VERIFICAÇÕES DE PRÉ-REQUISITOS (Fora do POST, para exibir erros de requisito) ---
    
    if regiao.id != jogador.regiao_residencia_id:
        flash("Você só pode abrir uma empresa na sua região de residência.", 'danger')
        return redirect(url_for('work.work_dashboard'))
    
    if jogador.nivel < 5:
        flash("Você deve atingir o Nível 5 para abrir sua primeira empresa.", 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    if len(jogador.empresas_proprias) >= jogador.get_max_empresas():
        flash(f"Você atingiu o limite de {jogador.get_max_empresas()} empresas para o seu nível.", 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    if jogador.gold < custo_gold or jogador.dinheiro < custo_money:
        msg = f"Você não tem fundos suficientes (Requer R$ {custo_money:,.0f} e G{custo_gold:.2f})."
        flash(msg, 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    # --- PROCESSAMENTO DO POST (Submissão do Formulário) ---
    
    if form.validate_on_submit():
        try:
            # 1. Subtração de custos
            jogador.gold -= custo_gold
            jogador.dinheiro -= custo_money
            
            # 2. Criação da Empresa
            nova_empresa = Empresa(
                regiao=regiao, 
                nome=form.nome.data,
                tipo='privada',
                proprietario_id=jogador.id, 
                taxa_lucro=form.taxa_lucro.data 
            )
            
            db.session.add(nova_empresa)

            descricao_acao = (
                f"Abertura de Empresa Privada '{form.nome.data}'. Custo: R${custo_money:,.0f} e G{custo_gold:.2f}."
            )
            
            hist = HistoricoAcao(
                jogador_id=jogador.id,
                tipo_acao='COMPRA_EMPRESA',
                descricao=descricao_acao,
                dinheiro_delta=-custo_money,
                gold_delta=-custo_gold
            )
            db.session.add(hist)

            db.session.commit()
            
            flash(f"PARABÉNS! Sua empresa '{nova_empresa.nome}' foi aberta!", 'success')
            return redirect(url_for('work.work_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erro fatal ao abrir empresa: {e}", 'danger')
            return redirect(url_for('work.work_dashboard'))
            
    # --- RENDERIZAÇÃO DO FORMULÁRIO (GET ou POST falha) ---
    
    return render_template('game_actions/open_company_form.html', 
                           title='Abrir Nova Empresa', 
                           form=form,
                           custos=custos, **footer)

@bp.route('/mine_gold/<int:empresa_id>', methods=['POST'])
@login_required
def mine_gold(empresa_id):
    jogador = Jogador.query.get(current_user.id)
    empresa = Empresa.query.get(empresa_id)
    regiao = jogador.regiao_atual
    
    if not regiao or not empresa or empresa.regiao_id != regiao.id:
        flash("Empresa inválida ou não está na sua região atual.", 'danger')
        return redirect(url_for('work.work_dashboard'))
    
    # 1. Obter a energia do formulário
    # ... (try/except para energia_gasta - Mantido) ...
    try:
        energia_gasta = int(request.form.get('energia_gasta', 0))
    except ValueError:
        flash("Valor de energia inválido.", 'danger')
        return redirect(url_for('profile.view_profile'))
    
    # --- 1. CALCULAR FATORES DE HABILIDADE (CORREÇÃO DE ESCOPO) ---
    fatores = calculate_player_factors(jogador) # <<< CHAMADA OBRIGATÓRIA AQUI!
    
    desconto_energia = fatores['desconto_energia']
    multiplicador_xp_educacao = fatores['multiplicador_xp_educacao']
    desconto_imposto = fatores['desconto_imposto']

    # --- 2. APLICAÇÃO DOS BÔNUS/DESCONTOS ---
    
    # A. Energia Gasta Efetiva (USANDO SAÚDE)
    energia_gasta_real = ceil(energia_gasta * (1.0 - desconto_energia)) 
    
    # B. Imposto Efetivo (USANDO FILANTROPIA)
    taxa_imposto_regional = regiao.taxa_imposto_geral
    taxa_imposto_efetiva = taxa_imposto_regional * (1.0 - desconto_imposto) # <-- IMPOSTO MENOR
    
    # C. CÁLCULO DE GANHO (MANTIDO)
    dinheiro_total_gerado = get_money_production(jogador.experiencia_trabalho) * (energia_gasta / 10.0) * FATOR_REDUCAO_DINHEIRO
    
    # D. DISTRIBUIÇÃO USANDO TAXA EFETIVA
    valor_imposto_dinheiro = dinheiro_total_gerado * taxa_imposto_efetiva 
    valor_imposto_gold = OURO_POR_ENERGIA * energia_gasta * taxa_imposto_efetiva
        
    # --- VERIFICAÇÕES DE PRÉ-REQUISITOS (Energia, Viagem, Reserva) ---
    
    if ViagemAtiva.query.filter_by(jogador_id=jogador.id).first():
        flash("Você está em viagem e não pode trabalhar!", 'warning')
        return redirect(url_for('map.view_map'))
        
    if energia_gasta < 10 or jogador.energia < energia_gasta:
        flash(f'Você precisa de no mínimo 10 energia e tem {jogador.energia}.', 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    if regiao.reserva_ouro <= 0:
        flash('As reservas de ouro desta região estão esgotadas!', 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    try:
        # --- CÁLCULO DA PRODUTIVIDADE E GANHOS ---
        
        # A. Valor Total de Dinheiro Gerado (R$)
        dinheiro_total_gerado = get_money_production(jogador.experiencia_trabalho) * (energia_gasta / 10.0) * FATOR_REDUCAO_DINHEIRO
        
        # B. Taxas, Lucros e Impostos
        taxa_imposto = regiao.taxa_imposto_geral
        taxa_lucro_empresa = empresa.taxa_lucro # Taxa definida pelo proprietário (Privada) ou a regra (Estatal)
        
        # 1. Imposto (Sempre pago ao governo/região, calculado sobre o BRUTO)
        valor_imposto_dinheiro = dinheiro_total_gerado * taxa_imposto
        valor_imposto_gold = OURO_POR_ENERGIA * energia_gasta * taxa_imposto # Novo cálculo: Gold também é taxado
        
        # 2. Lucro da Empresa (Pago à empresa, calculado sobre o BRUTO)
        valor_lucro_empresa_dinheiro = dinheiro_total_gerado * taxa_lucro_empresa
        valor_lucro_empresa_gold = OURO_POR_ENERGIA * energia_gasta * taxa_lucro_empresa # Novo cálculo: Gold também paga lucro

        # C. Dinheiro Líquido para o Jogador
        dinheiro_liquido_jogador = dinheiro_total_gerado - valor_imposto_dinheiro - valor_lucro_empresa_dinheiro
        gold_liquido_jogador = (OURO_POR_ENERGIA * energia_gasta) - valor_imposto_gold - valor_lucro_empresa_gold

        # XP GERAL E DE TRABALHO (Aplicando o Multiplicador de Educação)
        xp_trabalho_ganho_final = XP_TRABALHO_POR_ENERGIA * energia_gasta
        xp_geral_ganho_final = XP_GERAL_POR_ENERGIA * energia_gasta * multiplicador_xp_educacao
        
        # --- VERIFICAÇÃO DE LIQUIDEZ ---
        if dinheiro_liquido_jogador < 0 or gold_liquido_jogador < 0:
            flash('As taxas e lucros excedem o valor gerado. Trabalhe em outra região ou melhore sua XP.', 'warning')
            dinheiro_liquido_jogador = max(0.0, dinheiro_liquido_jogador)
            gold_liquido_jogador = max(0.0, gold_liquido_jogador)

        # D. Subtração de Reserva (Ação que afeta todas as empresas)
        esgotamento_total = ESGOTAMENTO_POR_ENERGIA * energia_gasta 
        regiao.reserva_ouro = max(0.0, regiao.reserva_ouro - esgotamento_total)

        # --- ATUALIZAÇÃO DO JOGADOR, EMPRESA E REGIÃO ---
        
        # 1. Jogador
        jogador.experiencia_trabalho += xp_trabalho_ganho_final
        jogador.experiencia += xp_geral_ganho_final
        jogador.last_status_update = datetime.utcnow()
        jogador.energia -= energia_gasta 
        jogador.dinheiro += dinheiro_liquido_jogador
        jogador.gold += gold_liquido_jogador
        
        # ... (Atualização de XP e Commit) ...
        if jogador.check_level_up():
            flash(f"PARABÉNS! Você alcançou o Nível {jogador.nivel}!", 'success')
        
        # Implantação da Regra do Imposto (Pago ao Governo/Região)
        if empresa.tipo == 'privada':
            # Fábrica Privada: Lucro da empresa (Dinheiro e Gold) vai para o proprietário.
            proprietario = empresa.proprietario
            if proprietario:
                proprietario.dinheiro += valor_lucro_empresa_dinheiro
                # O lucro em Gold da empresa vai para o proprietário
                proprietario.gold += valor_lucro_empresa_gold 
                db.session.add(proprietario)
        else: # Estatal
            # Fábrica Estatal: Lucro da empresa (Dinheiro) vai para o caixa da própria empresa (orçamento regional)
            empresa.dinheiro += valor_lucro_empresa_dinheiro
            # O Gold da empresa estatal é ignorado (ou vai para o caixa da estatal, mas mantemos apenas o dinheiro)

        # 3. Imposto (Sempre pago ao Governo/Região)
        estatal = regiao.empresas.filter_by(tipo='estatal').first()
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
        
        db.session.commit()
        
        flash(f"{descricao_acao}", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"Erro fatal ao trabalhar: {e}", 'danger')
        
    return redirect(url_for('work.work_dashboard'))

@bp.route('/mine_iron/<int:empresa_id>', methods=['POST'])
@login_required
def mine_iron(empresa_id):
    jogador = Jogador.query.get(current_user.id)
    empresa = Empresa.query.get(empresa_id)
    regiao = jogador.regiao_atual

    try:
        energia_gasta = int(request.form.get('energia_gasta', 0))
    except ValueError:
        flash("Valor de energia inválido.", 'danger')
        return redirect(url_for('work.work_dashboard'))
    
    # --- 1. CALCULAR FATORES DE HABILIDADE ---
    fatores = calculate_player_factors(jogador)
    desconto_energia = fatores['desconto_energia']
    multiplicador_xp_educacao = fatores['multiplicador_xp_educacao']

    # --- 2. APLICAÇÃO DOS BÔNUS/DESCONTOS ---
    
    # A. Energia Gasta Efetiva (USANDO SAÚDE)
    energia_gasta_real = ceil(energia_gasta * (1.0 - desconto_energia))
    
    # --- VERIFICAÇÕES DE PRÉ-REQUISITOS ---
    
    if ViagemAtiva.query.filter_by(jogador_id=jogador.id).first():
        flash("Você está em viagem e não pode trabalhar!", 'warning')
        return redirect(url_for('map.view_map'))
        
    if energia_gasta < 10 or jogador.energia < energia_gasta:
        flash(f'Você precisa de no mínimo 10 energia e tem {jogador.energia}.', 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    if regiao.reserva_ferro <= 0:
        flash('As reservas de ferro desta região estão esgotadas!', 'danger')
        return redirect(url_for('work.work_dashboard'))

    if empresa.produto != 'ferro':
        flash('Esta empresa não minera ferro.', 'danger')
        return redirect(url_for('work.work_dashboard'))
    
    if not regiao or not empresa or empresa.regiao_id != regiao.id:
        flash("Empresa inválida ou não está na sua região atual.", 'danger')
        return redirect(url_for('work.work_dashboard'))
    
    try:
        # --- CÁLCULO DE GANHO, ESGOTAMENTO E XP ---
        
        ferro_obtido = FERRO_POR_ENERGIA * energia_gasta
        
        xp_trabalho_ganho_final = XP_TRABALHO_POR_ENERGIA * energia_gasta
        xp_geral_ganho_base = XP_GERAL_POR_ENERGIA * energia_gasta
        xp_geral_ganho_final = xp_geral_ganho_base * multiplicador_xp_educacao

        # 1. ESGOOTAMENTO: Reduz a reserva regional
        esgotamento_total = ESGOTAMENTO_POR_ENERGIA * energia_gasta
        regiao.reserva_ferro = max(0.0, regiao.reserva_ferro - esgotamento_total) 

        # 2. REGISTRAR RECURSO NA MINA (À ESPERA DE TRANSPORTE)
        recurso_mina = RecursoNaMina.query.filter_by(
            jogador_id=jogador.id, 
            regiao_id=regiao.id,
            tipo_recurso='ferro'
        ).first()
        
        if not recurso_mina:
            recurso_mina = RecursoNaMina(
                jogador_id=jogador.id, regiao_id=regiao.id, tipo_recurso='ferro', quantidade=0.0, data_expiracao=datetime.utcnow() + timedelta(minutes=TEMPO_LIMITE_PLANEJAMENTO_MIN)
            )
            db.session.add(recurso_mina)
        else:
            recurso_mina.data_expiracao = datetime.utcnow() + timedelta(minutes=TEMPO_LIMITE_PLANEJAMENTO_MIN)
            
        recurso_mina.quantidade += ferro_obtido # Adiciona o ferro obtido

        # 3. ATUALIZAÇÃO DO JOGADOR (Gasto e XP)
        jogador.energia -= energia_gasta_real # <- USA A ENERGIA REAL
        jogador.experiencia_trabalho += xp_trabalho_ganho_final
        jogador.experiencia += xp_geral_ganho_final
        jogador.last_status_update = datetime.utcnow()

        if jogador.check_level_up():
            flash(f"PARABÉNS! Você alcançou o Nível {jogador.nivel}!", 'success')

        # 4. REGISTRO NO HISTÓRICO
        descricao_acao = (
            f"⛏️ Gastou {energia_gasta} E extraindo ferro em {empresa.nome} - {regiao.nome}. Lucro: {ferro_obtido:.0f} toneladas."
        )
        hist = HistoricoAcao(
            jogador_id=jogador.id, tipo_acao='MINERACAO',
            descricao=descricao_acao, dinheiro_delta=0.0, gold_delta=0.0
        )
        
        db.session.add_all([jogador, empresa, regiao, recurso_mina, hist])
        db.session.commit()

        # 5. FEEDBACK E REDIRECIONAMENTO PARA A GESTÃO DE TRANSPORTE
        flash(f"Mineração concluída! {ferro_obtido:.0f}t de Ferro estão prontas para transporte. Gerencie o transporte agora.", 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro fatal ao minerar ferro: {e}", 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    # Redireciona para o módulo de gestão de transporte, não para o dashboard de trabalho
    return redirect(url_for('warehouse.view_warehouse'))

@bp.route('/company/adjust_tax/<int:empresa_id>', methods=['POST'])
@login_required
def adjust_tax(empresa_id):
    jogador = Jogador.query.get(current_user.id)
    empresa = Empresa.query.get(empresa_id)
    
    nova_taxa = request.form.get('nova_taxa', type=float)

    # 1. Verificações de Segurança e Propriedade
    if not empresa or empresa.proprietario_id != jogador.id:
        flash("Acesso negado ou empresa não encontrada.", 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    if empresa.tipo == 'estatal':
        flash("Você não pode ajustar a taxa de lucro de empresas estatais.", 'danger')
        return redirect(url_for('work.work_dashboard'))
    
    # 2. Verificação do Limite de Tempo (6 horas)
    last_update = empresa.last_taxa_update
    if last_update is None:
        last_update = datetime.utcnow() - timedelta(days=365)

    time_since_last_update = datetime.utcnow() - last_update
        
    if time_since_last_update.total_seconds() < (6 * 3600): # 6 horas em segundos
        horas_restantes = ceil((6 * 3600 - time_since_last_update.total_seconds()) / 3600)
        flash(f"Você só pode ajustar a taxa de lucro a cada 6 horas. Restam aproximadamente {horas_restantes} horas.", 'warning')
        return redirect(url_for('work.work_dashboard'))

    # 3. Validação e Ação
    if 0.01 <= nova_taxa <= 0.99:
        try:
            empresa.taxa_lucro = nova_taxa
            empresa.last_taxa_update = datetime.utcnow()
            db.session.commit()
            flash(f"Taxa de lucro de {empresa.nome} ajustada para {nova_taxa*100:.0f}%.", 'success')
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar taxa: {e}", 'danger')
    else:
        flash("A taxa deve ser um valor entre 0.01 e 0.99.", 'danger')
        
    return redirect(url_for('work.work_dashboard'))

@bp.route('/start_transport', methods=['POST'])
@login_required
def start_transport():
    jogador = Jogador.query.get(current_user.id)
    armazem = jogador.armazem 
    
    # 1. Obter dados do POST e Objetos Críticos
    recurso_mina_id = request.form.get('recurso_mina_id', type=int)
    recurso_mina = RecursoNaMina.query.get(recurso_mina_id)
    
    if not recurso_mina or recurso_mina.jogador_id != jogador.id or not armazem:
        flash("Erro: O recurso a ser transportado não foi encontrado ou expirou.", 'danger')
        return redirect(url_for('warehouse.view_warehouse'))
    
    quantidade_total_pendente = recurso_mina.quantidade
    
    if quantidade_total_pendente <= 0:
        db.session.delete(recurso_mina); db.session.commit()
        flash("Recurso na mina zerado e removido.", 'info')
        return redirect(url_for('warehouse.view_warehouse'))
    
    try:
        # 2. CÁLCULO DE TEMPO BASE E DISTÂNCIA
        regiao_origem = recurso_mina.regiao; regiao_destino = armazem.regiao 
        distancia_km = calculate_distance_km(regiao_origem.latitude, regiao_origem.longitude, 
                                             regiao_destino.latitude, regiao_destino.longitude)

        tempo_minutos_base = TEMPO_TRANSPORTE_LOCAL_MIN
        if distancia_km >= 1.0:
            tempo_horas_base = (distancia_km / VELOCIDADE_BASE_KMH) * 2 
            tempo_minutos_base = ceil(tempo_horas_base * 60)
            tempo_minutos_base = max(TEMPO_TRANSPORTE_LOCAL_MIN, tempo_minutos_base)

        # 3. INICIALIZAÇÃO DE RASTREAMENTO E CUSTOS (CORRIGIDA)
        total_viagens_agendadas = 0
        recurso_coberto = 0.0
        custo_frete_total = 0.0
        
        transporte_jobs = [] 
        ultima_data_fim = datetime.utcnow()
        veiculo_disponivel_em = {v.id: datetime.utcnow() for v in armazem.frota.all()}

        # 4. ITERAÇÃO MESTRA: CALCULA CUSTO, TEMPO SEQUENCIAL E CRIA JOBS
        
        for key, viagens_value in request.form.items():
            if key.startswith('viagens_') and int(viagens_value) > 0:
                veiculo_id = int(key.split('_')[1])
                viagens_requeridas = int(viagens_value)
                veiculo = Veiculo.query.get(veiculo_id)

                if veiculo and not veiculo.transporte_atual:
                    custo_unitario_por_viagem = 0.0
                    
                    # 4a. CÁLCULO DE CUSTO PARA ESTE VEÍCULO
                    if distancia_km < 1.0:
                        custo_unitario_por_viagem = CUSTO_MINIMO_FRETE_LOCAL 
                    else:
                        # Frete = Custo por ton/km * Capacidade * Distância Ida
                        custo_unitario_por_viagem = veiculo.custo_tonelada_km * veiculo.capacidade * distancia_km 
                        
                    custo_frete_total += custo_unitario_por_viagem * viagens_requeridas
                    
                    # 4b. CÁLCULO DE TEMPO AJUSTADO AO VEÍCULO
                    tempo_ajuste_velocidade = 1.0 / veiculo.velocidade 
                    tempo_total_por_viagem = ceil(tempo_minutos_base * tempo_ajuste_velocidade)
                    tempo_total_por_viagem = max(TEMPO_TRANSPORTE_LOCAL_MIN, tempo_total_por_viagem)
                    
                    # 4c. SEQUENCIAMENTO E CRIAÇÃO
                    tempo_inicio = veiculo_disponivel_em[veiculo_id] # Pega o tempo que o veículo está livre (datetime)
                    
                    for i in range(viagens_requeridas):
            
                        # 1. Determina quanto recurso SOBRA na mina
                        recurso_ainda_pendente_na_mina = quantidade_total_pendente - recurso_coberto 
                        
                        # 2. A quantidade a transportar é o MIN(Capacidade do Veículo, Recurso Pendente)
                        quantidade_a_enviar = min(veiculo.capacidade, recurso_ainda_pendente_na_mina) # <<< CORREÇÃO AQUI
                        
                        # Se a quantidade a enviar for <= 0, paramos. (Isso deve ser evitado pelo front-end)
                        if quantidade_a_enviar <= 0.0:
                            break 
                            
                        data_fim_viagem = tempo_inicio + timedelta(minutes=tempo_total_por_viagem)
                        tempo_inicio = data_fim_viagem # Atualiza o rastreamento para a próxima viagem
                        
                        # CRIAÇÃO DO JOB
                        transporte = TransporteAtivo(
                            jogador_id=jogador.id, veiculo_id=veiculo.id, regiao_origem_id=regiao_origem.id,
                            regiao_destino_id=regiao_destino.id, tipo_recurso=recurso_mina.tipo_recurso,
                            quantidade=quantidade_a_enviar, data_fim=data_fim_viagem
                        )
                        transporte_jobs.append(transporte)
            
                        recurso_coberto += quantidade_a_enviar
                        total_viagens_agendadas += 1
                        
                        if data_fim_viagem > ultima_data_fim:
                            ultima_data_fim = data_fim_viagem
                    
                    # 4.3 Salva a ÚLTIMA data de fim DESTE VEÍCULO no rastreamento
                    veiculo_disponivel_em[veiculo_id] = tempo_inicio 

        # 5. VERIFICAÇÃO DE FUNDOS E SUBTRAÇÃO
        if jogador.dinheiro < custo_frete_total:
            flash(f"Dinheiro insuficiente para cobrir o frete. Custo total: {format_currency_python(custo_frete_total)}", 'danger')
            return redirect(url_for('warehouse.view_warehouse'))
        
        if total_viagens_agendadas == 0:
            flash("Nenhuma viagem agendada. Selecione os veículos e o número de viagens.", 'danger')
            return redirect(url_for('warehouse.view_warehouse'))

        # AÇÃO: Subtrai o custo TOTAL do frete
        jogador.dinheiro -= custo_frete_total
        
        # 6. VALIDAÇÃO FINAL E LIMPEZA
        
        if recurso_coberto < quantidade_total_pendente:
            recurso_restante = max(0.0, quantidade_total_pendente - recurso_coberto)
            recurso_mina.quantidade = recurso_restante

            TEMPO_EXPIRACAO_RECURSO_REMANESCENTE_HORAS = 6 
            recurso_mina.data_expiracao = datetime.utcnow() + timedelta(hours=TEMPO_EXPIRACAO_RECURSO_REMANESCENTE_HORAS)

            flash(f"AVISO: {recurso_restante:.0f} toneladas permanecerão na mina e expirarão em 6 horas.", 'warning')
            db.session.add(recurso_mina) 
        else:
             db.session.delete(recurso_mina) 
        
        descricao_acao = (
            f"Frete agendado para {total_viagens_agendadas} viagens. Custo: {format_currency_python(custo_frete_total)}."
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

        db.session.commit()
        
        # 7. FEEDBACK FINAL
        tempo_total_minutos_decorrido = ceil((ultima_data_fim - datetime.utcnow()).total_seconds() / 60)
        horas_display = int(tempo_total_minutos_decorrido // 60)
        minutos_display = int(tempo_total_minutos_decorrido % 60)
        
        flash(f"Logística iniciada! {total_viagens_agendadas} viagens agendadas. Custo: {format_currency_python(custo_frete_total)}. Conclusão total: {horas_display}h e {minutos_display}m.", 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao agendar transporte: {e}", "danger")
        
    return redirect(url_for('warehouse.view_warehouse'))
