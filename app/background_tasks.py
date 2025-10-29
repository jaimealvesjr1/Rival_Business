from flask import current_app
from app import db
from app.models import Jogador, TreinamentoAtivo, Regiao, RecursoNaMina
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload

MAX_ENERGIA = 200
ENERGIA_POR_MINUTO = 1

def replenish_resources(app):
    """Recarrega as reservas de recursos (ouro) das regiões a cada 6 horas."""
    with app.app_context():
        todas_regioes = Regiao.query.all()
        
        for regiao in todas_regioes:
            # Recarrega a reserva para o valor máximo (ou implemente uma lógica de recarga parcial)
            if regiao.reserva_ouro < regiao.reserva_ouro_max:
                regiao.reserva_ouro = regiao.reserva_ouro_max
                db.session.add(regiao)

        try:
            db.session.commit()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Reservas de recursos recarregadas.")
        except Exception as e:
            db.session.rollback()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro ao recarregar recursos: {e}")

def update_region_indices(app):
    """
    Calcula e atualiza os índices de todas as regiões (Educacao, Saude, Desenvolvimento, Imposto).
    """
    with app.app_context():
        from app import db 
        from app.models import Jogador, Regiao 
        
        # 1. OBTER DADOS GLOBAIS DE HABILIDADE DOS JOGADORES RESIDENTES
        jogadores_residentes = Jogador.query.filter(
            Jogador.regiao_residencia_id.isnot(None)
        ).all()
        
        habilidades_por_regiao = {}
        
        # Totais Globais
        total_global = {'educacao': 0.0, 'saude': 0.0, 'filantropia': 0.0}
        
        for jogador in jogadores_residentes:
            residencia_id = jogador.regiao_residencia_id
            
            if residencia_id not in habilidades_por_regiao:
                habilidades_por_regiao[residencia_id] = {'educacao': 0.0, 'saude': 0.0, 'filantropia': 0.0}
            
            # Soma as habilidades na localização e globalmente
            habilidades_por_regiao[residencia_id]['educacao'] += jogador.habilidade_educacao
            habilidades_por_regiao[residencia_id]['saude'] += jogador.habilidade_saude
            habilidades_por_regiao[residencia_id]['filantropia'] += jogador.habilidade_filantropia
            
            total_global['educacao'] += jogador.habilidade_educacao
            total_global['saude'] += jogador.habilidade_saude
            total_global['filantropia'] += jogador.habilidade_filantropia

        # Soma total dos 3 índices globalmente (necessário para o ID)
        soma_global_id = total_global['educacao'] + total_global['saude'] + total_global['filantropia']
        
        # 2. CALCULAR PROPORÇÕES E ATUALIZAR REGIÕES
        todas_regioes = Regiao.query.all()

        for regiao in todas_regioes:
            regiao_id = regiao.id
            
            # Habilidades da Localização (ou 0 se vazia)
            habilidades_regiao = habilidades_por_regiao.get(regiao_id, {'educacao': 0.0, 'saude': 0.0, 'filantropia': 0.0})
            
            # --- CÁLCULO DAS PROPORÇÕES (0.00 a 1.00) ---
            
            # Índice de Educação
            if total_global['educacao'] > 0:
                regiao.indice_educacao = habilidades_regiao['educacao'] / total_global['educacao']
            else:
                regiao.indice_educacao = 0.0
                
            # Índice de Saúde
            if total_global['saude'] > 0:
                regiao.indice_saude = habilidades_regiao['saude'] / total_global['saude']
            else:
                regiao.indice_saude = 0.0

            # Índice de Filantropia
            if total_global['filantropia'] > 0:
                regiao.indice_filantropia = habilidades_regiao['filantropia'] / total_global['filantropia']
            else:
                regiao.indice_filantropia = 0.0
                
            # --- CÁLCULO DO ÍNDICE DE DESENVOLVIMENTO (ID) ---
            
            soma_regiao_id = (
                habilidades_regiao['educacao'] + 
                habilidades_regiao['saude'] + 
                habilidades_regiao['filantropia']
            )
            
            if soma_global_id > 0:
                # ID = (Soma Localização / Soma Global) * 10
                indice_dev = (soma_regiao_id / soma_global_id) * 10 
                indice_dev = max(1.0, min(10.0, indice_dev)) 
            else:
                indice_dev = 1.0 
                
            regiao.indice_desenvolvimento = indice_dev
            
            # 3. Calcular Imposto (Taxa)
            regiao.calcular_taxa_imposto() 
            
            db.session.add(regiao)

        try:
            db.session.commit()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Índices de Regiões atualizados. ID Global: {soma_global_id:.2f}")
        except Exception as e:
            db.session.rollback()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro ao atualizar índices regionais: {e}")

def regenerate_player_status(app):
    """
    Função de background para regenerar energia e atualizar status dos jogadores.
    """
    with app.app_context():
        from app import db
        from app.models import Jogador, TreinamentoAtivo, ViagemAtiva, PedidoResidencia, Armazem, ArmazemRecurso, TransporteAtivo
        from datetime import datetime, timedelta
        # 2. Busca todos os jogadores
        jogadores = Jogador.query.all()

        for jogador in jogadores:
            
            regiao_atual = jogador.regiao_atual
            if not regiao_atual: continue

            multiplicador_saude = 1.0 + regiao_atual.indice_saude 
            
            # Ganho: 1 E/min * (1 + Bônus)
            energia_ganha_por_minuto = ENERGIA_POR_MINUTO * multiplicador_saude
            
            if jogador.energia < MAX_ENERGIA:
                time_difference: timedelta = datetime.utcnow() - jogador.last_status_update
                minutes_passed = int(time_difference.total_seconds() // 60)
                
                if minutes_passed > 0:
                    energia_regenerada = minutes_passed * energia_ganha_por_minuto 
                    energia_a_somar = int(energia_regenerada)
                    nova_energia = min(jogador.energia + energia_a_somar, MAX_ENERGIA)
                    time_remainder = time_difference.total_seconds() % 60
                    
                    jogador.energia = int(nova_energia)
                    jogador.last_status_update = datetime.utcnow() - timedelta(seconds=time_remainder) 
                    
                    db.session.add(jogador)

        treinos_concluidos = TreinamentoAtivo.query.filter(
            TreinamentoAtivo.data_fim <= datetime.utcnow()
        ).all()
        
        for treino in treinos_concluidos:
            jogador = Jogador.query.get(treino.jogador_id) # Acessa o jogador pelo ID
            
            if jogador:
                # 1. Aumenta o nível da habilidade
                skill_attr = f'habilidade_{treino.habilidade}'
                # O Nível Alvo é o que deve ser aplicado
                setattr(jogador, skill_attr, treino.nivel_alvo) 
                
                # 2. Adiciona XP (Exemplo)
                jogador.experiencia += 500
                
                # Adiciona o jogador para salvar a XP/Nível
                db.session.add(jogador) 
                
                # NÃO USE flash() aqui, pois não há contexto de requisição. 
                # (Assumimos que você já removeu os flashes daqui)
                
            # 3. Remove o registro de treino ativo (mesmo que o jogador seja None)
            db.session.delete(treino)

        viagens_concluidas = ViagemAtiva.query.filter(
            ViagemAtiva.data_fim <= datetime.utcnow()
        ).all()
        
        for viagem in viagens_concluidas:
            jogador = Jogador.query.get(viagem.jogador_id)
            
            if jogador:
                # 1. Move o jogador para o novo destino
                jogador.regiao_atual_id = viagem.destino_id
                
                # 2. Informação para o log
                destino_nome = Regiao.query.get(viagem.destino_id).nome
                print(f"Viagem concluída: Jogador {jogador.username} moveu-se para {destino_nome}.")
                db.session.add(jogador)
                
            # 3. Remove o registro de viagem ativa
            db.session.delete(viagem)

        pedidos_aprovados = PedidoResidencia.query.filter(
            PedidoResidencia.data_aprovacao <= datetime.utcnow()
        ).all()
        
        for pedido in pedidos_aprovados:
            jogador = Jogador.query.get(pedido.jogador_id)
            regiao_destino = Regiao.query.get(pedido.regiao_destino_id)
            
            if jogador and regiao_destino:
                # 1. Altera a residência do jogador
                jogador.regiao_residencia_id = regiao_destino.id
                print(f"Residência de {jogador.username} aprovada para {regiao_destino.nome}.")
                db.session.add(jogador)
            
            # 2. Remove o registro de pedido ativo
            db.session.delete(pedido)
        
        transportes_concluidos = TransporteAtivo.query.filter(
            TransporteAtivo.data_fim <= datetime.utcnow()
        ).all()
        
        for transporte in transportes_concluidos:
            jogador = Jogador.query.get(transporte.jogador_id)
            armazem = jogador.armazem
            
            if jogador and armazem:
                # 1. Credita o recurso no Armazém
                recurso = armazem.recursos.filter_by(tipo=transporte.tipo_recurso).first()
                if not recurso:
                    recurso = ArmazemRecurso(armazem_id=armazem.id, tipo=transporte.tipo_recurso, quantidade=0.0)
                    db.session.add(recurso)

                recurso.quantidade += transporte.quantidade
                
                # 2. Log
                print(f"Transporte concluído: {transporte.quantidade:.0f} {transporte.tipo_recurso} creditados no armazém de {jogador.username}.")
                db.session.add(armazem)
                
            # 3. Remove o registro de transporte ativo
            db.session.delete(transporte)

        for jogador in jogadores:
            
            # Cálculo da regeneração de ENERGIA
            
            # Se a energia já está no máximo, não há o que fazer
            if jogador.energia >= MAX_ENERGIA:
                continue

            # Tempo decorrido desde a última atualização
            time_difference: timedelta = datetime.utcnow() - jogador.last_status_update
            
            # Minutos completos passados
            minutes_passed = int(time_difference.total_seconds() // 60)

            if minutes_passed > 0:
                # 1 Energia por minuto * Minutos passados
                energia_regenerada = minutes_passed * ENERGIA_POR_MINUTO
                
                # Calcula a nova energia (limitada ao máximo)
                nova_energia = min(jogador.energia + energia_regenerada, MAX_ENERGIA)
                
                # Calcula o tempo que ainda deve ser considerado para a próxima regeneração
                # Subtrai o tempo usado para a regeneração atual
                time_remainder = time_difference.total_seconds() % 60
                
                # 3. Atualiza o jogador
                jogador.energia = nova_energia
                
                # Atualiza o timestamp (voltando o tempo que não foi usado na regeneração)
                # Ex: se passaram 65 segundos (1 min regenerado), atualizamos o last_status_update
                # para 5 segundos atrás, para que ele espere os 55 segundos restantes.
                jogador.last_status_update = datetime.utcnow() - timedelta(seconds=time_remainder) 

                db.session.add(jogador)
        
        # 4. Salva as alterações no banco de dados
        try:
            db.session.commit()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Status/Treinos processados. Concluídos: {len(treinos_concluidos)}")
        except Exception as e:
            db.session.rollback()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ERRO NO COMMIT DE BACKGROUND: {e}")
            raise 
        finally:
            db.session.remove()

def clean_expired_resources(app):
    """Deleta recursos minerados que expiraram (não foram agendados em 15 minutos)."""
    with app.app_context():
        from app import db # Acessa a instância do DB
        
        expired_resources = RecursoNaMina.query.filter(
            RecursoNaMina.data_expiracao <= datetime.utcnow()
        ).all()

        if expired_resources:
            for recurso in expired_resources:
                # Opcional: Adicionar log para saber o que foi deletado
                print(f"[{datetime.now().strftime('%H:%M:%S')}] RECURSO EXPIRADO: {recurso.quantidade:.0f}t de {recurso.tipo} de Jogador {recurso.jogador_id} deletado.")
                db.session.delete(recurso)
            
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro ao deletar recursos expirados: {e}")

def run_core_status_updates(app):
    """
    Função mestra para executar todos os jobs de alta frequência (60 segundos).
    """
    # 1. Regeneração de Status e Conclusão de Treino/Viagem (CRÍTICO)
    regenerate_player_status(app)
    
    # 2. Atualização de Índices Regionais (Necessário para taxas/bônus)
    update_region_indices(app)
    
    # 3. Limpeza de Recursos Expirados (Manutenção)
    clean_expired_resources(app)