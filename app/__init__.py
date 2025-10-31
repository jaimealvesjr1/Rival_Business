from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_apscheduler import APScheduler
from flask_migrate import Migrate
from flask_bootstrap import Bootstrap
from pytz import timezone
from datetime import datetime
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

# Inicialização das Extensões
db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
scheduler = APScheduler()
migrate = Migrate()
bootstrap = Bootstrap()

# Configurações do Flask-Login
login_manager.login_view = 'auth.login' 
login_manager.login_message_category = 'info'
login_manager.login_message = 'Faça login para acessar.'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicializa as extensões com a aplicação
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    bootstrap.init_app(app)

    from app.background_tasks import run_core_status_updates, replenish_resources, check_vehicle_validity

    scheduler.init_app(app)
    scheduler.start()
    # 1. JOB DE RECARGA DE RECURSOS (6 HORAS) - MANTIDO SEPARADO
    if not scheduler.get_job('resource_replenishment'):
        scheduler.add_job(id='resource_replenishment', 
                          func=replenish_resources, 
                          args=[app], 
                          trigger='interval', 
                          hours=6,
                          name='Recarga de Reservas de Recursos')
                          
    # 2. JOB MESTRE DE STATUS (CONSOLIDA OS 3 JOBS DE 60 SEGUNDOS)
    if not scheduler.get_job('core_status_update'):
        scheduler.add_job(id='core_status_update', 
                          func=run_core_status_updates, 
                          args=[app],
                          trigger='interval', 
                          seconds=60, # Frequência de 1 minuto
                          name='Atualização de Status Central (60s)')
    
    if not scheduler.get_job('vehicle_validity_check'):
        scheduler.add_job(id='vehicle_validity_check', 
                          func=check_vehicle_validity, 
                          args=[app],
                          trigger='interval', 
                          hours=1, # 1 hora para testes
                          name='Checagem de Validade de Veículos')
        
    ACAO_MAP = {
        'MINERACAO': 'Mineração',
        'COMPRA_EMPRESA': 'Abertura de Empresa',
        'TREINO': 'Treinamento de Habilidade',
        'VIAGEM': 'Viagem',
        'RESIDENCIA_PEDIDO': 'Solicitação de Residência',
        'RESIDENCIA_CANCEL': 'Residência Cancelada',
        'FRETE_COBRADO': 'Custo de Frete',
        'VEICULO_COMPRA': 'Compra de Veículo',
        'VEICULO_VENCIDO': 'Veículo Expirado',
        'ARMAZEM_UPGRADE': 'Melhoria de Armazém',
        'TRANSPORTE_INICIO': 'Logística Agendada',
        'TRANSPORTE_CONCLUIDO': 'Transporte Concluído',
    }

    @app.template_filter('action_format')
    def action_format_filter(action_code):
        """Converte o código de ação (MINERACAO) para um nome amigável."""
        return ACAO_MAP.get(action_code, action_code.replace('_', ' ').capitalize())

    @app.template_filter('datetime_local')
    def format_datetime_to_local(utc_dt):
        """Converte um objeto datetime UTC para o fuso horário da aplicação (Brasil)."""
        
        # 1. Define os fusos horários
        utc_zone = timezone(config_class.TIMEZONE_SERVER)
        app_zone = timezone(config_class.TIMEZONE_APP)
        
        # 2. Converte o objeto datetime (presume-se que o objeto no DB está sem timezone info, então forçamos UTC)
        # Primeiro, fazemos aware (consciente) que o dt é UTC
        utc_dt_aware = utc_zone.localize(utc_dt)
        
        # 3. Converte para o fuso horário local (Brasil)
        local_dt = utc_dt_aware.astimezone(app_zone)
        
        # 4. Retorna no formato legível
        return local_dt.strftime('%d/%m/%Y %H:%M:%S')
    
    @app.template_filter('currency_format') # <-- CORRIGIDO: Agora usa 'currency_format'
    def currency_format_filter(value, prefix='R$', separator='.', places=0):
        """Formata valores de dinheiro (R$ e $) no formato X.XXX."""
        
        valor_arredondado = int(round(value))
        valor_formatado = f"{valor_arredondado:,}".replace(',', separator)
        
        return f"{prefix} {valor_formatado}"

    # Registro de Blueprints (Módulos)

    from app.manage import bp as manage_bp
    app.register_blueprint(manage_bp)
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.profile import bp as profile_bp
    app.register_blueprint(profile_bp)
    
    from app.skill_development import bp as skill_development_bp
    app.register_blueprint(skill_development_bp)

    from app.game_actions import bp as game_actions_bp
    app.register_blueprint(game_actions_bp)

    from app.work import bp as work_bp
    app.register_blueprint(work_bp)

    from app.map import bp as map_bp
    app.register_blueprint(map_bp)

    from app.warehouse import bp as warehouse_bp
    app.register_blueprint(warehouse_bp)

    from app.market import bp as market_bp
    app.register_blueprint(market_bp)

    from app import cli_commands
    app.cli.add_command(cli_commands.init_db_command)

    with app.app_context():       
        db.create_all()
    
    # Rota de teste/index (temporária)
    from flask import render_template, redirect, url_for
    
    @app.route('/')
    def index():
        from flask_login import current_user
        
        # 1. Toca a variável current_user para garantir que a sessão é carregada.
        # Se estiver autenticado, redireciona para o perfil.
        if current_user.is_authenticated:
            return redirect(url_for('profile.view_profile'))
        
        # 2. Se não estiver logado, exibe a página de boas-vindas.
        return render_template('index.html', title='Boas-Vindas', **footer)

    return app