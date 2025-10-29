from app import create_app
from config import Config

app = create_app(Config)

if __name__ == '__main__':
    # Cria o arquivo do banco de dados e as tabelas (se não existirem)
    with app.app_context():
        from app.models import Jogador, Regiao, Empresa, Armazem, Veiculo, TipoVeiculo
        from app import db
        db.create_all() 
        
        # --- Lógica de Inicialização de Dados ---
        
        # 1. Cria a primeira localização
        regiao_inicial = Regiao.query.first()
        if not regiao_inicial:
            print("Criando Localização Inicial 'Centro-Oeste de Minas'...")
            regiao_inicial = Regiao(nome='Centro-Oeste de Minas', latitude=-19.8785, longitude=-44.9844)
            db.session.add(regiao_inicial)
            db.session.commit()
            print(f"Localização '{regiao_inicial.nome}' criada com sucesso!")

        todas_regioes = Regiao.query.all()
        
        recursos_estatais = [
            {'nome': 'Mina de Ouro', 'tipo_produto': 'ouro', 'taxa_lucro': 0.30},
            {'nome': 'Mina de Ferro', 'tipo_produto': 'ferro', 'taxa_lucro': 0.30},
        ]
        modelos_veiculos = [
            {'tipo': 'caminhao_3_4', 'display': 'Caminhão 3/4', 'cap': 3, 'vel': 1.0, 'custo_tk': 808, 'validade': 4, 'nivel_req': 1, 'ferro': 25, 'money': 50000, 'gold': 5},
            {'tipo': 'caminhao_toco', 'display': 'Caminhão Toco', 'cap': 6, 'vel': 0.9, 'custo_tk': 551, 'validade': 5, 'nivel_req': 5, 'ferro': 120, 'money': 150000, 'gold': 15},
            {'tipo': 'caminhao_truck', 'display': 'Caminhão Truck', 'cap': 16, 'vel': 0.8, 'custo_tk': 313, 'validade': 6, 'nivel_req': 10, 'ferro': 240, 'money': 400000, 'gold': 40},
            {'tipo': 'carreta', 'display': 'Carreta', 'cap': 35, 'vel': 0.6, 'custo_tk': 173, 'validade': 7, 'nivel_req': 15, 'ferro': 500, 'money': 750000, 'gold': 75},
            {'tipo': 'bitrem', 'display': 'Bitrem', 'cap': 45, 'vel': 0.5, 'custo_tk': 157, 'validade': 7, 'nivel_req': 20, 'ferro': 800, 'money': 1000000, 'gold': 100},
            {'tipo': 'rodotrem', 'display': 'Rodotrem', 'cap': 55, 'vel': 0.5, 'custo_tk': 144, 'validade': 8, 'nivel_req': 25, 'ferro': 1000, 'money': 1500000, 'gold': 150},
        ]

        # --- FASE 2: CRIAÇÃO DE MODELOS ESTÁTICOS (TIPOS DE VEÍCULOS) ---
        novos_tipos_criados = 0
        for modelo in modelos_veiculos:
            if not TipoVeiculo.query.filter_by(tipo_veiculo=modelo['tipo']).first():
                db.session.add(TipoVeiculo(
                    tipo_veiculo=modelo['tipo'], nome_display=modelo['display'],
                    capacidade=modelo['cap'], velocidade=modelo['vel'],
                    custo_tonelada_km=modelo['custo_tk'], validade_dias=modelo['validade'],
                    nivel_especializacao_req=modelo['nivel_req'],
                    custo_ferro=modelo['ferro'], custo_money=modelo['money'], custo_gold=modelo['gold']
                ))
                novos_tipos_criados += 1
        
        if novos_tipos_criados > 0:
            db.session.commit()
            print(f"SUCESSO: {novos_tipos_criados} Tipos de Veículos adicionados.")

        # 3. CONSULTA CRÍTICA: Carrega o tipo de veículo inicial APÓS o commit
        caminhao_3_4_tipo = TipoVeiculo.query.filter_by(tipo_veiculo='caminhao_3_4').first()
        
        if not caminhao_3_4_tipo:
            print("ERRO CRÍTICO: TipoVeiculo 'caminhao_3_4' não encontrado. O Armazém inicial FALHARÁ.")
        
        # --- FASE 4: CRIAÇÃO DE EMPRESAS ESTATAIS (OURO/FERRO) ---
        novas_empresas_criadas = 0
        for regiao in todas_regioes:
            for recurso in recursos_estatais:
                
                empresa_existente = Empresa.query.filter_by(
                    regiao_id=regiao.id, 
                    tipo='estatal',
                    produto=recurso['tipo_produto']
                ).first()
                
                if not empresa_existente:
                    print(f"Criando {recurso['nome']} na localização: {regiao.nome}")
                    nova_empresa = Empresa(
                        regiao_id=regiao.id,
                        nome=f"{recurso['nome']} - {regiao.nome}",
                        tipo='estatal',
                        produto=recurso['tipo_produto'],
                        taxa_lucro=recurso['taxa_lucro'], 
                        dinheiro=0.0
                    )
                    db.session.add(nova_empresa)
                    novas_empresas_criadas += 1
        
        if novas_empresas_criadas > 0:
            db.session.commit()
            print(f"SUCESSO: {novas_empresas_criadas} Empresas Estatais criadas/corrigidas.")

        # --- FASE 5: CRIAÇÃO DO ADMIN E ARMAZÉM INICIAL ---

        # 5a. Cria o primeiro Administrador (Se não existir)
        admin_user = Jogador.query.filter_by(username='Admin').first()
        if not admin_user:
            print("Criando usuário administrador padrão (username: admin)...")
            
            # Necessário para usar o set_password, que precisa do modelo Jogador
            admin_user = Jogador(
                username='Admin',
                is_admin=True,
                regiao_residencia_id=regiao_inicial.id,
                regiao_atual_id=regiao_inicial.id
            )
            # Use uma senha temporária
            admin_user.set_password('327122') 
            
            db.session.add(admin_user)
            
            # ** COMMIT IMEDIATO APÓS A CRIAÇÃO DO ADMIN (MAIS SEGURO)**
            try:
                db.session.commit()
                print("Administrador criado com sucesso! Use /admin para gerenciar.")
            except Exception as e:
                db.session.rollback()
                # Se o erro de integridade ocorrer AQUI, é porque outro código está a criar admin.
                print(f"Erro de Integridade ao criar Admin: {e}")

        # 5b. GARANTIR ARMAZÉM E VEÍCULO INICIAL
        todos_jogadores = Jogador.query.all()
        novos_objetos_armazem = 0
        
        for jogador in todos_jogadores:
            if not jogador.armazem:
                print(f"Criando Armazém para o jogador: {jogador.username}")
                
                armazem = Armazem(jogador_id=jogador.id, regiao_id=jogador.regiao_residencia_id)
                db.session.add(armazem)
                db.session.flush() # CRÍTICO: Gera o ID do Armazém

                # Veículo inicial: AGORA 'caminhao_3_4_tipo' ESTÁ DEFINIDO E CHECADO
                if caminhao_3_4_tipo:
                    veiculo_inicial = Veiculo(
                        armazem_id=armazem.id,
                        nome=caminhao_3_4_tipo.nome_display,
                        tipo_veiculo=caminhao_3_4_tipo.tipo_veiculo,
                        capacidade=caminhao_3_4_tipo.capacidade,
                        velocidade=caminhao_3_4_tipo.velocidade,
                        custo_tonelada_km=caminhao_3_4_tipo.custo_tonelada_km,
                        validade_dias=caminhao_3_4_tipo.validade_dias,
                        nivel_especializacao_req=caminhao_3_4_tipo.nivel_especializacao_req
                    )
                    db.session.add(veiculo_inicial)
                    novos_objetos_armazem += 1

        if novos_objetos_armazem > 0:
            try:
                db.session.commit()
                print(f"SUCESSO: {novos_objetos_armazem} Armazéns e Veículos iniciais criados.")
            except Exception as e:
                db.session.rollback()
                print(f"Erro ao criar Armazém/Veículo: {e}")
        
        # --- Fim da Lógica de Inicialização de Dados ---

    # app.run(debug=True)
