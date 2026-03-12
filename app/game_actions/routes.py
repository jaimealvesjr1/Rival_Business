from flask import redirect, url_for, flash, request, render_template, current_app
from flask_login import login_required, current_user
from app import db
from app.utils import calculate_distance_km, format_currency_python
from app.models import (Regiao, Jogador, ViagemAtiva, PedidoResidencia, Empresa, 
                        Armazem, ArmazemRecurso, HistoricoAcao, TransporteAtivo, 
                        Veiculo, RecursoNaMina, CampoAgricola, PlantioAtivo)
from app.services import mining_service, player_service, farming_service, logistics_service, manufacturing_service
from app.game_actions import bp
from app.game_actions.forms import OpenCompanyForm, OpenCampoForm
from datetime import datetime, timedelta
from math import ceil
from config import Config
import math

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

@bp.route('/travel', methods=['POST'])
@login_required
def travel():
    jogador = Jogador.query.get(current_user.id)
    regiao_atual = jogador.regiao_atual
    
    destino_id = request.form.get('destino_id', type=int)
    destino = Regiao.query.get(destino_id)
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
    
    if not armazem:
        flash("Erro crítico: Armazém não inicializado.", 'danger')
        return redirect(url_for('warehouse.view_warehouse'))
    
    form_data = request.form

    try:
        success, message, ultima_data_fim, custo_frete_total, total_viagens_agendadas = logistics_service.schedule_transport(
            jogador=jogador,
            armazem=armazem,
            form_data=form_data
        )
        if success:
            db.session.commit()

            if message.startswith("AVISO"):
                flash(message, 'warning')
            
            tempo_total_minutos_decorrido = math.ceil((ultima_data_fim - datetime.utcnow()).total_seconds() / 60)
            horas_display = int(tempo_total_minutos_decorrido // 60)
            minutos_display = int(tempo_total_minutos_decorrido % 60)

            flash(f"Logística iniciada! {total_viagens_agendadas} viagens agendadas. Custo: {format_currency_python(custo_frete_total)}. Conclusão total: {horas_display}h e {minutos_display}m.", 'success')
        
        else:
            db.session.rollback()
            flash(message, 'danger')

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao agendar transporte: {e}", "danger")
    
    return redirect(url_for('warehouse.view_warehouse'))

@bp.route('/manufacture/<int:empresa_id>', methods=['POST'])
@login_required
def start_manufacture(empresa_id):
    jogador = Jogador.query.get(current_user.id)
    empresa = Empresa.query.get(empresa_id)
    
    # Verificação de propriedade (apenas o proprietário pode iniciar a produção)
    if not empresa or empresa.proprietario_id != jogador.id:
        flash("Acesso negado ou empresa não encontrada.", 'danger')
        return redirect(url_for('work.work_dashboard'))
    
    # 1. Obter dados do formulário
    try:
        recipe_id = int(request.form.get('recipe_id'))
        cycles = int(request.form.get('cycles'))
    except (ValueError, TypeError):
        flash("Dados de produção inválidos.", 'danger')
        return redirect(url_for('work.work_dashboard'))

    # 2. Chamar o serviço
    try:
        success, message = manufacturing_service.start_manufacturing(
            jogador=jogador,
            empresa=empresa,
            recipe_id=recipe_id,
            cycles=cycles
        )
        
        if success:
            db.session.commit()
            flash(message, 'success')
        else:
            db.session.rollback()
            flash(message, 'danger')

    except Exception as e:
        db.session.rollback()
        flash(f"Erro fatal ao iniciar produção: {e}", 'danger')
        
    return redirect(url_for('work.work_dashboard'))

@bp.route('/campo/open', methods=['GET', 'POST']) 
@login_required
def open_campo_view():
    jogador = Jogador.query.get(current_user.id)
    regiao = jogador.regiao_residencia 
    form = OpenCampoForm()
    
    # Obter os custos (definido no Modelo Jogador, Fase 1)
    custos = jogador.get_open_campo_cost()
    custo_gold = custos['gold']
    custo_money = custos['money']
    
    # --- VERIFICAÇÕES DE PRÉ-REQUISITOS ---
    if regiao.id != jogador.regiao_residencia_id:
        flash("Você só pode comprar campos na sua região de residência.", 'danger')
        return redirect(url_for('work.work_dashboard'))
    
    if jogador.nivel < 2: # Regra 3 (1 campo a cada 2 níveis)
        flash("Você deve atingir o Nível 2 para comprar seu primeiro campo.", 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    if len(jogador.campos_proprios) >= jogador.get_max_campos():
        flash(f"Você atingiu o limite de {jogador.get_max_campos()} campos para o seu nível.", 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    if jogador.gold < custo_gold or jogador.dinheiro < custo_money:
        msg = f"Você não tem fundos suficientes (Requer R$ {custo_money:,.0f} e G{custo_gold:.2f})."
        flash(msg, 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    # --- PROCESSAMENTO DO POST ---
    if form.validate_on_submit():
        try:
            jogador.gold -= custo_gold
            jogador.dinheiro -= custo_money
            
            novo_campo = CampoAgricola(
                regiao=regiao, 
                nome=form.nome.data,
                proprietario_id=jogador.id, 
                taxa_lucro=form.taxa_lucro.data 
            )
            
            db.session.add(novo_campo)
            db.session.commit()
            
            flash(f"Parabéns! Seu campo '{novo_campo.nome}' foi comprado!", 'success')
            return redirect(url_for('work.work_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erro fatal ao comprar campo: {e}", 'danger')
            return redirect(url_for('work.work_dashboard'))
            
    # --- RENDERIZAÇÃO DO FORMULÁRIO (GET) ---
    return render_template('game_actions/open_campo_form.html', 
                           title='Comprar Novo Campo', 
                           form=form,
                           custos=custos, **footer)


@bp.route('/plant_corn/<int:campo_id>', methods=['POST'])
@login_required
def plant_corn(campo_id):
    jogador = Jogador.query.get(current_user.id)
    campo = db.session.get(CampoAgricola, campo_id)
    
    if not campo:
        flash("Campo agrícola não encontrado.", 'danger')
        return redirect(url_for('work.work_dashboard'))
        
    if ViagemAtiva.query.filter_by(jogador_id=jogador.id).first():
        flash("Você está em viagem e não pode plantar!", 'warning')
        return redirect(url_for('map.view_map'))

    try:
        energia_gasta = int(request.form.get('energia_gasta', 0))
    except ValueError:
        flash("Valor de energia inválido.", 'danger')
        return redirect(url_for('work.work_dashboard'))

    try:
        # --- CHAMA O SERVIÇO ---
        success, message = farming_service.start_planting(
            jogador=jogador,
            campo=campo,
            energia_gasta=energia_gasta
        )
        
        if success:
            db.session.commit()
            flash(message, 'success')
        else:
            db.session.rollback() # Desfaz a cobrança de custos se o serviço falhou
            flash(message, 'danger')

    except Exception as e:
        db.session.rollback()
        flash(f"Erro fatal ao plantar: {e}", 'danger')

    return redirect(url_for('work.work_dashboard'))