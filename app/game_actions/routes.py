from flask import redirect, url_for, flash, request, render_template, current_app
from flask_login import login_required, current_user
from app import db
from app.utils import calculate_distance_km, format_currency_python
from app.models import Regiao, Jogador, ViagemAtiva, PedidoResidencia, Empresa, Armazem, ArmazemRecurso, HistoricoAcao, TransporteAtivo, Veiculo, RecursoNaMina
from app.services import mining_service, player_service
from app.game_actions import bp
from app.game_actions.forms import OpenCompanyForm
from datetime import datetime, timedelta
from math import ceil
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}


@bp.route('/travel', methods=['POST'])
@login_required
def travel():
    jogador = Jogador.query.get(current_user.id)
    regiao_atual = jogador.regiao_atual
    
    destino_id = request.form.get('destino_id', type=int)
    destino = Regiao.query.get(destino_id),
    NIVEL_MINIMO_PARA_VIAGEM = 2

    if jogador.nivel < NIVEL_MINIMO_PARA_VIAGEM:
        flash(f"Você precisa do Nível {NIVEL_MINIMO_PARA_VIAGEM} para viajar entre regiões.", 'danger')
        return redirect(url_for('map.view_map'))

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
    tempo_ajustado_min = current_app.config['TEMPO_BASE_ESPERA_MIN'] * (1.0 - desconto_percentual)
    
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

    try:
        energia_gasta = int(request.form.get('energia_gasta', 0))
    except ValueError:
        flash("Valor de energia inválido.", 'danger')
        return redirect(url_for('work.work_dashboard'))

    # --- VERIFICAÇÕES DE PRÉ-REQUISITOS (Lógica de Rota) ---
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
        # --- CHAMA O SERVIÇO ---
        success, message, levelup = mining_service.mine_gold_action(
            jogador=jogador,
            empresa=empresa,
            regiao=regiao,
            energia_gasta=energia_gasta
        )
        # -------------------------

        if not success:
            # Caso o serviço retorne um erro de negócio
            flash(message, 'warning')
        else:
            # O serviço foi bem-sucedido, então commitamos as mudanças
            db.session.commit()
            flash(message, 'success')
            if levelup:
                flash(f"PARABÉNS! Você alcançou o Nível {jogador.nivel}!", 'success')

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
    
    # --- VERIFICAÇÕES DE PRÉ-REQUISITOS (Lógica de Rota) ---
    
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
        # --- CHAMA O SERVIÇO ---
        success, message, levelup = mining_service.mine_iron_action(
            jogador=jogador,
            empresa=empresa,
            regiao=regiao,
            energia_gasta=energia_gasta
        )
        # -------------------------

        # O serviço foi bem-sucedido, então commitamos as mudanças
        # (O 'success' aqui é sempre True, mas mantemos o padrão)
        db.session.commit()
        
        flash(f"Mineração concluída! {message.split('Lucro: ')[1]} estão prontas para transporte. Gerencie o transporte agora.", 'success')
        
        if levelup:
            flash(f"PARABÉNS! Você alcançou o Nível {jogador.nivel}!", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"Erro fatal ao minerar ferro: {e}", 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    # Redireciona para o módulo de gestão de transporte (armazém)
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
    
    # 1. Obter dados do POST (Região + Tipo)
    regiao_id = request.form.get('regiao_id', type=int)
    tipo_recurso = request.form.get('tipo_recurso', type=str)
    
    # 2. Buscar TODOS os recursos pendentes nesse grupo
    recursos_para_transportar = RecursoNaMina.query.filter_by(
        jogador_id=jogador.id,
        regiao_id=regiao_id,
        tipo_recurso=tipo_recurso
    ).all()

    if not recursos_para_transportar or not armazem:
        flash("Recursos para transporte não encontrados ou expiraram.", 'danger')
        return redirect(url_for('warehouse.view_warehouse'))

    # 3. Calcular a quantidade total
    quantidade_total_pendente = sum(r.quantidade for r in recursos_para_transportar)
    
    if quantidade_total_pendente <= 0:
        for r in recursos_para_transportar: db.session.delete(r)
        db.session.commit()
        flash("Recursos na mina zerados e removidos.", 'info')
        return redirect(url_for('warehouse.view_warehouse'))
    
    # Salva a região de origem (do primeiro item, já que são agrupados)
    regiao_origem = recursos_para_transportar[0].regiao
    
    try:
        # 2. CÁLCULO DE TEMPO BASE E DISTÂNCIA
        regiao_origem = db.session.get(Regiao, regiao_id) 
        regiao_destino = armazem.regiao 
        
        if not regiao_origem:
             flash("Região de origem não encontrada.", 'danger')
             return redirect(url_for('warehouse.view_warehouse'))

        distancia_km = calculate_distance_km(regiao_origem.latitude,
                                             regiao_origem.longitude, 
                                             regiao_destino.latitude,
                                             regiao_destino.longitude)

        tempo_minutos_base = current_app.config['TEMPO_TRANSPORTE_LOCAL_MIN']
        if distancia_km >= 1.0:
            tempo_horas_base = (distancia_km / current_app.config['VELOCIDADE_BASE_KMH']) * 2 
            tempo_minutos_base = ceil(tempo_horas_base * 60)
            tempo_minutos_base = max(current_app.config['TEMPO_TRANSPORTE_LOCAL_MIN'], tempo_minutos_base)

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
                        custo_unitario_por_viagem = current_app.config['CUSTO_MINIMO_FRETE_LOCAL'] 
                    else:
                        # Frete = Custo por ton/km * Capacidade * Distância Ida
                        custo_unitario_por_viagem = veiculo.custo_tonelada_km * veiculo.capacidade * distancia_km 
                        
                    custo_frete_total += custo_unitario_por_viagem * viagens_requeridas
                    
                    # 4b. CÁLCULO DE TEMPO AJUSTADO AO VEÍCULO
                    tempo_ajuste_velocidade = 1.0 / veiculo.velocidade 
                    tempo_total_por_viagem = ceil(tempo_minutos_base * tempo_ajuste_velocidade)
                    tempo_total_por_viagem = max(current_app.config['TEMPO_TRANSPORTE_LOCAL_MIN'], tempo_total_por_viagem)
                    
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
                            regiao_destino_id=regiao_destino.id, tipo_recurso=tipo_recurso,
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
             
             # Deleta todos os antigos e cria um NOVO registro com o restante
             for r in recursos_para_transportar:
                 db.session.delete(r)
             
             expiracao_min = current_app.config['RECURSO_NA_MINA_EXPIRACAO_MIN']
             
             novo_remanescente = RecursoNaMina(
                 jogador_id=jogador.id,
                 regiao_id=regiao_id,
                 tipo_recurso=tipo_recurso,
                 quantidade=recurso_restante,
                 data_expiracao = datetime.utcnow() + timedelta(minutes=expiracao_min)
             )
             db.session.add(novo_remanescente)
             
             flash(f"AVISO: {recurso_restante:.0f}t permanecerão na mina. Frete cobrado.", 'warning')
        else:
             # Deleta todos os recursos do grupo, pois foram 100% transportados
             for r in recursos_para_transportar:
                 db.session.delete(r)
        
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
