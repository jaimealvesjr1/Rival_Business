import os
from datetime import timedelta, datetime

class Config:
    # Chave Secreta
    # ESSENCIAL para segurança do Flask (sessões, forms, etc.)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'rival-business-mr-james'
    
    # Usaremos SQLite para começar (um único arquivo)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///site.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SERVER_NAME = '127.0.0.1:5000'
    
    TIMEZONE_SERVER = 'UTC' 
    TIMEZONE_APP = 'America/Sao_Paulo'
    VERSAO_APP = 'Development'
    ANO_ATUAL = datetime.now().year

    SCHEDULER_API_ENABLED = True
    SCHEDULER_JOB_DEFAULTS = {
        'coalesce': True,
        'max_instances': 1
    }
    SCHEDULER_EXECUTORS = {
        'default': {'type': 'threadpool', 'max_workers': 20}
    }
    
    # Configurações do Flask-Admin
    FLASK_ADMIN_SWATCH = 'cerulean' # Tema visual
    
    # Configurações do Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    UPLOAD_FOLDER = os.path.join('app', 'static')

    # --- CONSTANTES DE BALANCEAMENTO DO JOGO ---
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
    MILHO_POR_ENERGIA = 2.0             # 2t de Milho por 10 Energia (Base)

    FATOR_REDUCAO_DINHEIRO = 1

    TEMPO_BASE_ESPERA_MIN = 360
    TEMPO_ESPERA_RESIDENCIA_HORAS = 6

    VELOCIDADE_BASE_KMH = 100
    HORA_POR_KM = 100 
    CUSTO_POR_KM = 15.0
    TEMPO_TRANSPORTE_LOCAL_MIN = 5
    CUSTO_MINIMO_FRETE_LOCAL = 500
    RECURSO_NA_MINA_EXPIRACAO_MIN = 360

    MARKET_ORDER_DURATION_HOURS = 72            # Ordens expiram em 3 dias

    FARMING_COST_MONEY_PER_10_ENERGY = 1000.0   # Custo (R$) para plantar (Regra 1)
    FARMING_GROW_TIME_MINUTES = 60              # Tempo de crescimento (Regra 2)
    FARMING_FIELD_MAX_SLOTS = 2                 # Slots por campo (Regra 4)
    FARMING_FIELD_MAX_USES = 6                  # Usos antes do descanso
    FARMING_FIELD_REST_HOURS = 6                # Horas de descanso
    FARMING_XP_PER_10_ENERGY = 15.0             # XP de trabalho ganho (15 XP por 10 E)
