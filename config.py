import os
from datetime import timedelta, datetime

class Config:
    # Chave Secreta
    # ESSENCIAL para segurança do Flask (sessões, forms, etc.)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'rival-business-mr-james'
    
    # Configuração do Banco de Dados
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
