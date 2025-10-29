from app import db, login_manager
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Loader de Usuário para Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """Carrega um usuário pelo ID para o Flask-Login."""
    return Jogador.query.get(int(user_id))

# 1. ENTIDADE JOGADOR
class Jogador(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # *** ADIÇÃO PARA O ADMIN ***
    is_admin = db.Column(db.Boolean, default=False)
    # *************************
    
    # Recursos e Atributos Iniciais
    dinheiro = db.Column(db.Float, default=1000.00)
    gold = db.Column(db.Float, default=5.00)
    energia = db.Column(db.Integer, default=200) 
    nivel = db.Column(db.Integer, default=1)
    experiencia = db.Column(db.Float, default=0.0)
    experiencia_trabalho = db.Column(db.Float, default=0.0)
    
    # Colunas de Habilidades
    habilidade_educacao = db.Column(db.Float, default=0.0)
    habilidade_filantropia = db.Column(db.Float, default=0.0)
    habilidade_saude = db.Column(db.Float, default=0.0)

    # Localização (Requer a Entidade Localização)
    regiao_residencia_id = db.Column(db.Integer, db.ForeignKey('regiao.id'), nullable=True) 
    regiao_atual_id = db.Column(db.Integer, db.ForeignKey('regiao.id'), nullable=True)

    # Coluna para tracking de background (regeneração)
    last_status_update = db.Column(db.DateTime, default=datetime.utcnow) 
    
    # Relacionamentos
    regiao_residencia = db.relationship(
        'Regiao',
        foreign_keys=[regiao_residencia_id],
        backref=db.backref('residentes')
    )
    regiao_atual = db.relationship(
        'Regiao', 
        foreign_keys=[regiao_atual_id], 
        backref=db.backref('jogadores_presentes', lazy='dynamic')
    )
    armazem = db.relationship(
        'Armazem',
        backref='proprietario', uselist=False)

    treino_ativo = db.relationship('TreinamentoAtivo', 
                                   backref='jogador', 
                                   uselist=False, 
                                   lazy='select')
    
    def check_level_up(self):
        """Verifica se o jogador pode subir de nível e o faz, se possível."""
        
        leveled_up = False
        
        while self.experiencia >= self.get_xp_needed_for_next_level():
            self.nivel += 1
            leveled_up = True
            
        return leveled_up

    def get_xp_needed_for_next_level(self):
        """
        Calcula o XP TOTAL acumulado necessário para o PRÓXIMO nível geral,
        usando a regra: Nv 1 = 6000, Multiplicador = 2.25
        """
        
        # O cálculo deve ser baseado no NÍVEL QUE O JOGADOR VAI ALCANÇAR (self.nivel + 1)
        nivel_alvo = self.nivel + 1 
        base_xp = 6000.0
        multiplicador = 2.25
        
        if nivel_alvo <= 1:
            return base_xp
            
        # Fórmula: XP Base * (Multiplicador ^ (Nível Alvo - 1))
        # Nv 1 -> 6000 * (2.25 ^ 0) = 6000
        # Nv 2 -> 6000 * (2.25 ^ 1) = 13500
        # Nv 3 -> 6000 * (2.25 ^ 2) = 30375
        
        xp_total_necessaria = base_xp * (multiplicador ** (nivel_alvo - 1)) 
        
        return round(xp_total_necessaria, 0)
    
    def get_skill_cost(self, skill_name, current_skill_level):
        """Calcula o custo e o tempo para o próximo nível de uma habilidade."""

        base_cost = 1000.00
        base_time_minutes = 10

        # A cada nível, aumenta 20% no preço e no tempo
        # Ex: Nível 1: base * (1.2 ^ 0)
        # Ex: Nível 2: base * (1.2 ^ 1)

        multiplicador = 1.2 ** current_skill_level

        custo = round(base_cost * multiplicador, 2)
        tempo = round(base_time_minutes * multiplicador)

        return {'custo': custo, 'tempo_minutos': tempo}

    def get_max_empresas(self):
        """Calcula o número máximo de empresas que o jogador pode possuir."""
        # A primeira só pode ser aberta no Nv 5. Uma empresa a cada 5 níveis.
        if self.nivel < 5:
            return 0
        
        # Fórmula: (Nível Atual // 5)
        # Nv 5-9: 1 empresa. Nv 10-14: 2 empresas, etc.
        return self.nivel // 5

    def get_open_company_cost(self):
        """Calcula o custo atual (Gold e Dinheiro) para abrir uma nova empresa."""
        
        # Custo Base (Mantido)
        base_gold = 100.0
        base_money = 2000000.0
        
        # CORREÇÃO: Usar len() para contar o número de empresas na lista
        num_empresas_atuais = len(self.empresas_proprias) 
        
        # Aumento de 25% a cada nova empresa (25% por empresa já possuída)
        multiplicador_aumento = 1.25 ** num_empresas_atuais
        
        cost_gold = round(base_gold * multiplicador_aumento, 2)
        cost_money = round(base_money * multiplicador_aumento, 2)
        
        return {'gold': cost_gold, 'money': cost_money}

    # Métodos para senha (usaremos Flask-Bcrypt)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Métodos exigidos pelo Flask-Login
    # O método 'get_id' já é fornecido pelo 'UserMixin' se o 'id' for int
    def is_active(self):
        return True
    
    def __repr__(self):
        return f'<Jogador {self.username} - Nv {self.nivel}>'

# 2. ENTIDADE REGIÃO 
class Regiao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)

    latitude = db.Column(db.Float, nullable=False, default=-18.0)
    longitude = db.Column(db.Float, nullable=False, default=-44.0)

    reserva_ouro = db.Column(db.Float, default=10000.0)
    reserva_ouro_max = db.Column(db.Float, default=10000.0)

    reserva_ferro = db.Column(db.Float, default=10000.0)
    reserva_ferro_max = db.Column(db.Float, default=10000.0)

    empresas = db.relationship('Empresa', 
                               backref='regiao', 
                               lazy='dynamic',
                               cascade='all, delete-orphan')
    
    indice_educacao = db.Column(db.Float, default=0.0) 
    indice_saude = db.Column(db.Float, default=0.0)
    indice_filantropia = db.Column(db.Float, default=0.0)
    
    # ID: Permanece, mas será baseado na soma dos três.
    indice_desenvolvimento = db.Column(db.Float, default=1.0)

    taxa_imposto_geral = db.Column(db.Float, default=0.05)

    def __repr__(self):
        return f'<Regiao {self.nome}>'
    
    def calcular_taxa_imposto(self):
        """Calcula a taxa de imposto com base no indice_desenvolvimento (1 a 10)."""
        
        # Arredonda o índice para o inteiro mais próximo (para a regra de imposto)
        idx = round(self.indice_desenvolvimento)
        
        if idx >= 10:
            taxa = 0.01  # 1%
        elif idx >= 7:
            taxa = 0.05  # 5%
        elif idx >= 4:
            taxa = 0.10  # 10%
        elif idx >= 2:
            taxa = 0.15  # 15%
        else:
            taxa = 0.20  # 20% (Índice 1)
            
        self.taxa_imposto_geral = taxa
        return taxa
    
class TreinamentoAtivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign Key para o jogador
    jogador_id = db.Column(db.Integer, 
                           db.ForeignKey('jogador.id'), 
                           unique=True, 
                           nullable=False)
    
    # Habilidade sendo treinada (ex: 'educacao', 'saude')
    habilidade = db.Column(db.String(50), nullable=False)
    
    # Nível alvo (para o qual o jogador está treinando)
    nivel_alvo = db.Column(db.Float, nullable=False)
    
    # Momento em que o treino deve ser concluído
    data_fim = db.Column(db.DateTime, nullable=False) 

    def __repr__(self):
        return f'<Treino: Jogador {self.jogador_id} -> {self.habilidade} (Nv {self.nivel_alvo})>'

class Empresa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    regiao_id = db.Column(db.Integer, db.ForeignKey('regiao.id'), nullable=False)
    
    nome = db.Column(db.String(100))
    
    # Tipo: 'estatal' ou 'privada'
    tipo = db.Column(db.String(50), default='estatal')
    produto = db.Column(db.String(50))
    
    # Proprietário (FK para Jogador se for 'privada'. Nulo se for 'estatal'.)
    proprietario_id = db.Column(db.Integer, db.ForeignKey('jogador.id'), nullable=True)
    
    # Porcentagem que a fábrica ganha do ouro minerado (Será o triplo da taxa de imposto para estatais)
    taxa_lucro = db.Column(db.Float, default=0.30)
    last_taxa_update = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Orçamento da fábrica
    dinheiro = db.Column(db.Float, default=0.0)

    # Relacionamento de volta para o jogador proprietário
    proprietario = db.relationship('Jogador', backref='empresas_proprias')

    def __repr__(self):
        return f'<Empresa ({self.tipo.capitalize()}) {self.nome} em Localização {self.regiao_id}>'

class ViagemAtiva(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign Key para o jogador
    jogador_id = db.Column(db.Integer, 
                           db.ForeignKey('jogador.id'), 
                           unique=True, 
                           nullable=False)
    
    destino_id = db.Column(db.Integer, db.ForeignKey('regiao.id'), nullable=False)
    
    # Momento em que a viagem deve ser concluída
    data_fim = db.Column(db.DateTime, nullable=False) 

    # RELACIONAMENTO: Conecta ViagemAtiva ao Jogador
    jogador = db.relationship('Jogador', backref='viagem_ativa', uselist=False) 
    
    # RELACIONAMENTO: Conecta ao Destino
    destino = db.relationship('Regiao', backref='viagens_destino', foreign_keys=[destino_id])

    def __repr__(self):
        return f'<Viagem: Jogador {self.jogador_id} -> Destino {self.destino_id}>'

class PedidoResidencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogador.id'), unique=True, nullable=False)
    regiao_destino_id = db.Column(db.Integer, db.ForeignKey('regiao.id'), nullable=False)
    
    # Momento em que o pedido será aprovado (6 horas após o pedido)
    data_aprovacao = db.Column(db.DateTime, nullable=False) 

    jogador = db.relationship('Jogador', backref='pedido_residencia_ativo', uselist=False)
    regiao_destino = db.relationship('Regiao', foreign_keys=[regiao_destino_id])

    def __repr__(self):
        return f'<PedidoResidencia: Jogador {self.jogador_id} para Localização {self.regiao_destino_id}>'

class HistoricoAcao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogador.id'), nullable=False)
    
    # Tipo de ação (e.g., 'MINERACAO', 'COMPRA_EMPRESA', 'TREINO', 'VIAGEM')
    tipo_acao = db.Column(db.String(50), nullable=False)
    
    # Descrição para o usuário (e.g., "Ganhou R$ 10.000 (Lucro Líquido)")
    descricao = db.Column(db.String(255), nullable=False)
    
    # Momento da ação
    timestamp = db.Column(db.DateTime, default=datetime.utcnow) 
    
    # Opcional: registrar os valores envolvidos para relatórios
    dinheiro_delta = db.Column(db.Float, default=0.0) # Positivo para ganho, negativo para custo
    gold_delta = db.Column(db.Float, default=0.0)
    
    # Relacionamento para acesso fácil ao jogador
    jogador = db.relationship('Jogador', backref=db.backref('historico_acoes', order_by=timestamp.desc()))

    def __repr__(self):
        return f'<Ação {self.tipo_acao} por Jogador {self.jogador_id}>'
    
class Armazem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogador.id'), unique=True, nullable=False)
    
    # Residência fixa do armazém (Local de onde as viagens de transporte partem/chegam)
    regiao_id = db.Column(db.Integer, db.ForeignKey('regiao.id'), nullable=False)
    
    # Capacidade: Níveis (para calcular capacidade/frota/especialização)
    nivel_capacidade = db.Column(db.Integer, default=1)
    nivel_frota = db.Column(db.Integer, default=1)
    nivel_especializacao = db.Column(db.Integer, default=1)
    
    # Recursos Armazenados (One-to-Many: Um armazém pode ter vários tipos de recursos)
    recursos = db.relationship('ArmazemRecurso', backref='armazem', lazy='dynamic')
    
    # Veículos do Armazém (frota)
    frota = db.relationship('Veiculo', backref='armazem', lazy='dynamic')
    regiao = db.relationship('Regiao', backref='armazens_residenciais')

    def get_upgrade_cost(self, nivel_atual):
        """Calcula o custo base (Gold, Dinheiro, Tempo) para o próximo nível."""
        
        # Base: R$10.000, 20 Gold, 30 minutos
        base_money = 10000.0
        base_gold = 20.0
        base_time_minutes = 30 
        
        # Aumento de 20% a cada nível (Nível 1 usa multiplicador de 1.2^0)
        multiplicador = 1.2 ** (nivel_atual - 1)
        
        custo_money = round(base_money * multiplicador, 2)
        custo_gold = round(base_gold * multiplicador, 2)
        tempo_minutos = round(base_time_minutes * multiplicador)
        
        return {'money': custo_money, 'gold': custo_gold, 'time_minutes': tempo_minutos}

    def get_capacidade_upgrade_info(self):
        """Retorna custo e efeitos para o próximo Nível Capacidade."""
        nivel = self.nivel_capacidade
        cost = self.get_upgrade_cost(nivel)
        
        return {
            'next_level': nivel + 1,
            'money': cost['money'],
            'gold': cost['gold'],
            'time': cost['time_minutes'],
            'effect': f"+5% - Total: {self.get_capacidade_max() * 1.05:.0f} Toneladas."
        }
    
    def get_frota_upgrade_info(self):
        """Retorna custo e efeitos para o próximo Nível Frota."""
        nivel = self.nivel_frota
        cost = self.get_upgrade_cost(nivel)
        
        proximo_nivel = nivel + 1
        
        # Verifica se o próximo nível desbloqueia uma vaga extra (a cada 5 níveis)
        desbloqueia_vaga = (proximo_nivel % 5 == 0) 
        
        effect = f"+1 Vaga de Frota"
        if desbloqueia_vaga:
            effect += f" (+1 Vaga de Frota Total: {self.get_max_frota() + 1})"
            
        return {
            'next_level': proximo_nivel,
            'money': cost['money'],
            'gold': cost['gold'],
            'time': cost['time_minutes'],
            'effect': effect
        }

    def get_especializacao_upgrade_info(self):
        """Retorna custo e efeitos para o próximo Nível Especialização."""
        nivel = self.nivel_especializacao
        cost = self.get_upgrade_cost(nivel)
        
        proximo_nivel = nivel + 1
        
        # Verifica se o próximo nível desbloqueia algum veículo (Ex: Nv 5, 10, 15...)
        # Aqui, vamos focar apenas no aumento de nível, e o template fará a verificação de compra.
        
        return {
            'next_level': proximo_nivel,
            'money': cost['money'],
            'gold': cost['gold'],
            'time': cost['time_minutes'],
            'effect': f"Desbloqueia veículos mais avançados"
        }
    
    # ------------------ MÉTODOS DE CÁLCULO DE ARMAZÉM ------------------
    BASE_CAPACIDADE = 1000.0 # Capacidade inicial de 1000 toneladas
    
    def get_capacidade_max(self):
        """Calcula a capacidade total com base no nível de Capacidade (5% por nível)."""
        # (Nível - 1) porque o Nível 1 já começa com a BASE
        multiplicador = 1 + (self.nivel_capacidade - 1) * 0.05 
        return round(self.BASE_CAPACIDADE * multiplicador, 0)
    
    def get_max_frota(self):
        """Calcula o número máximo de veículos (1 vaga a cada 5 níveis, começando com 1)."""
        if self.nivel_frota < 5:
            return 1
            
        vagas_extras = self.nivel_frota // 5
        
        return 1 + vagas_extras

class ArmazemRecurso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    armazem_id = db.Column(db.Integer, db.ForeignKey('armazem.id'), nullable=False)
    
    # Tipo de Recurso (e.g., 'ferro', 'petroleo')
    tipo = db.Column(db.String(50), nullable=False, unique=True) # Unique no tipo para cada armazém
    quantidade = db.Column(db.Float, default=0.0)

class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    armazem_id = db.Column(db.Integer, db.ForeignKey('armazem.id'), nullable=False)
    
    nome = db.Column(db.String(80), nullable=False)
    tipo_veiculo = db.Column(db.String(80), nullable=False) # Ex: 'caminhao_3_4', 'carreta'
    
    capacidade = db.Column(db.Float, nullable=False) # Toneladas que pode transportar
    velocidade = db.Column(db.Float, nullable=False) # Multiplicador de velocidade (1.0 = normal)
    custo_tonelada_km = db.Column(db.Float, nullable=False) # Custo operacional por tonelada/km
    
    # Duração e Nível
    data_compra = db.Column(db.DateTime, default=datetime.utcnow)
    validade_dias = db.Column(db.Integer, nullable=False) # Duração (ex: 30 dias)
    nivel_especializacao_req = db.Column(db.Integer, default=1) # Nível do Armazém necessário

class TipoVeiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    tipo_veiculo = db.Column(db.String(80), unique=True, nullable=False) # Chave única (e.g., 'carreta')
    nome_display = db.Column(db.String(80), nullable=False) # Nome para exibir (e.g., Carreta)
    
    # Especificações do Veículo
    capacidade = db.Column(db.Float, nullable=False) 
    velocidade = db.Column(db.Float, nullable=False) 
    custo_tonelada_km = db.Column(db.Float, nullable=False) 
    validade_dias = db.Column(db.Integer, nullable=False)
    
    # Requisitos de Compra
    custo_ferro = db.Column(db.Float, default=0.0) # NOVO CUSTO (usa o minério de ferro)
    custo_money = db.Column(db.Float, default=0.0)
    custo_gold = db.Column(db.Float, default=0.0)
    
    nivel_especializacao_req = db.Column(db.Integer, default=1)
    
    # O veículo real criado (Veiculo) terá um relacionamento com esta tabela
    
    def __repr__(self):
        return f'<TipoVeiculo {self.nome_display} - {self.capacidade}t>'

class TransporteAtivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogador.id'), nullable=False)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculo.id'), nullable=False)
    
    regiao_origem_id = db.Column(db.Integer, db.ForeignKey('regiao.id'), nullable=False)
    regiao_destino_id = db.Column(db.Integer, db.ForeignKey('regiao.id'), nullable=False) # Armazém
    
    tipo_recurso = db.Column(db.String(50), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    
    data_fim = db.Column(db.DateTime, nullable=False) 

    # Relações
    jogador = db.relationship('Jogador', backref='transporte_ativo')
    veiculo = db.relationship('Veiculo', backref='transporte_atual', uselist=False)

    def __repr__(self):
        return f'<Transporte: {self.tipo_recurso} por Veículo {self.veiculo_id}>'

class RecursoNaMina(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogador.id'), nullable=False)
    regiao_id = db.Column(db.Integer, db.ForeignKey('regiao.id'), nullable=False)

    data_expiracao = db.Column(db.DateTime, nullable=False)
    
    tipo_recurso = db.Column(db.String(50), nullable=False) # e.g., 'ferro', 'ouro'
    quantidade = db.Column(db.Float, default=0.0)

    # Relacionamentos
    jogador = db.relationship('Jogador', backref='recursos_na_mina')
    regiao = db.relationship('Regiao', backref='recursos_minerados')
    
    def __repr__(self):
        return f'<RecursoNaMina: {self.quantidade:.0f} {self.tipo_recurso} em Região {self.regiao_id}>'