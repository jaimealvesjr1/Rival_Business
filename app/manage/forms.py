from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField, BooleanField, SelectField, IntegerField, PasswordField
from wtforms.validators import DataRequired, NumberRange, Length, Optional
from app.models import Regiao, Jogador

class RegionForm(FlaskForm):
    """Formulário para criar uma nova Localização."""
    nome = StringField('Nome da Localização', validators=[DataRequired()])
    
    latitude = FloatField('Latitude', 
                          default=-18.0,
                          validators=[DataRequired(), NumberRange(min=-90, max=90)])
    longitude = FloatField('Longitude', 
                           default=-44.0,
                           validators=[DataRequired(), NumberRange(min=-180, max=180)])
                           
    reserva_ouro_max = FloatField('Reserva Máxima de Ouro', 
                                  default=10000.0,
                                  validators=[DataRequired(), NumberRange(min=0)])
    reserva_ferro_max = FloatField('Reserva Máxima de Ferro', 
                                  default=10000.0,
                                  validators=[DataRequired(), NumberRange(min=0)])
                                    
    submit = SubmitField('Criar Localização')

class RegionEditForm(FlaskForm):
    nome = StringField('Nome da Localização', validators=[DataRequired(), Length(min=2)])
    
    # Coordenadas e Reservas
    latitude = FloatField('Latitude', validators=[DataRequired(), NumberRange(min=-90, max=90)])
    longitude = FloatField('Longitude', validators=[DataRequired(), NumberRange(min=-180, max=180)])
    reserva_ouro_max = FloatField('Reserva Máxima de Ouro', validators=[DataRequired(), NumberRange(min=0)])
    reserva_ferro_max = FloatField('Reserva Máxima de Ferro', validators=[DataRequired(), NumberRange(min=0)]) # <-- NOVO CAMPO
    reserva_ouro = FloatField('Reserva Atual de Ouro', validators=[DataRequired(), NumberRange(min=0)])
    reserva_ferro = FloatField('Reserva Atual de Ferro', validators=[DataRequired(), NumberRange(min=0)])

    # Índices (Admin pode ajustá-los manualmente em caso de debug, mas o background os recalcula)
    indice_desenvolvimento = FloatField('Índice Desenvolvimento', validators=[NumberRange(min=1, max=10)])
    taxa_imposto_geral = FloatField('Taxa de Imposto Geral', validators=[NumberRange(min=0, max=1)])

    submit = SubmitField('Salvar Alterações')

class PlayerForm(FlaskForm):
    username = StringField('Nome de Usuário', validators=[DataRequired(), Length(min=2, max=80)])
    password = StringField('Senha', validators=[DataRequired(), Length(min=6)])
    is_admin = BooleanField('É Administrador?', default=False)
    
    # SelectField para Localização (para definir a residência e localização atual)
    regiao_id = SelectField('Localização Inicial (Residência/Atual)', coerce=int, validators=[DataRequired()])

    submit = SubmitField('Criar Jogador')

    def __init__(self, *args, **kwargs):
        super(PlayerForm, self).__init__(*args, **kwargs)
        # Preenche as opções do SelectField dinamicamente
        self.regiao_id.choices = [(r.id, r.nome) for r in Regiao.query.all()]
        if not self.regiao_id.choices:
             self.regiao_id.choices = [(0, 'Nenhuma Localização Disponível')]

class PlayerEditForm(FlaskForm):
    # Campos que podem ser editados
    username = StringField('Nome de Usuário', validators=[DataRequired(), Length(min=2, max=80)])
    is_admin = BooleanField('É Administrador?', default=False)
    
    # Recurso e Habilidades (Apenas para o Admin ajustar)
    dinheiro = FloatField('Dinheiro', validators=[NumberRange(min=0)])
    gold = FloatField('Gold', validators=[NumberRange(min=0)])
    energia = IntegerField('Energia', validators=[NumberRange(min=0, max=200)])
    nivel = IntegerField('Nível', validators=[NumberRange(min=1)])
    experiencia = FloatField('Experiência Geral')
    experiencia_trabalho = FloatField('Experiência de Trabalho')
    
    # Senha: Opcional, apenas para redefinir
    new_password = PasswordField('Nova Senha (Preencha para mudar)', validators=[Optional(), Length(min=6)])
    
    # SelectField para Localização (Residência e Atual)
    regiao_residencia_id = SelectField('Localização de Residência', coerce=int, validators=[DataRequired()])
    regiao_atual_id = SelectField('Localização Atual', coerce=int, validators=[DataRequired()])

    submit = SubmitField('Salvar Alterações')

    def __init__(self, *args, **kwargs):
        super(PlayerEditForm, self).__init__(*args, **kwargs)
        # Preenche as opções do SelectField dinamicamente
        regioes = Regiao.query.all()
        choices = [(r.id, r.nome) for r in regioes]
        if not choices:
             choices = [(0, 'Nenhuma Localização Disponível')]
             
        self.regiao_residencia_id.choices = choices
        self.regiao_atual_id.choices = choices

class CompanyAdminForm(FlaskForm):
    # Como as estatais são automáticas, este é focado na criação de empresas privadas
    nome = StringField('Nome da Empresa', validators=[DataRequired(), Length(min=3, max=50)])
    produto = SelectField('Produção', choices=[('ouro', 'Extração de Ouro'),
                                              ('ferro', 'Mineração de Ferro')
                                              ],validators=[DataRequired()])
    taxa_lucro = FloatField('Taxa de Lucro (0.01 a 0.99)', default=0.15, validators=[DataRequired(), NumberRange(min=0.01, max=0.99)])
    
    # Opcional: Permitir ao admin criar empresas em qualquer lugar
    regiao_id = SelectField('Localização da Empresa', coerce=int, validators=[DataRequired()])
    
    # Opcional: Definir o proprietário (o admin pode criar empresas para outros jogadores)
    proprietario_id = SelectField('Proprietário (Jogador ID)', coerce=int, validators=[DataRequired()])
    
    submit = SubmitField('Criar Empresa')

    def __init__(self, *args, **kwargs):
        super(CompanyAdminForm, self).__init__(*args, **kwargs)
        from app.models import Regiao, Jogador
        self.regiao_id.choices = [(r.id, r.nome) for r in Regiao.query.all()]
        # Lista todos os jogadores para definir o proprietário
        self.proprietario_id.choices = [(j.id, f'{j.id}: {j.username}') for j in Jogador.query.all()]

class CompanyEditForm(FlaskForm):
    nome = StringField('Nome da Empresa', validators=[DataRequired(), Length(min=3, max=50)])
    tipo = SelectField('Tipo', choices=[('estatal', 'Estatal'), ('privada', 'Privada')], validators=[DataRequired()])
    
    # Proprietário (pode ser None para Estatal)
    proprietario_id = SelectField('Proprietário (Jogador ID)', coerce=int, validators=[Optional()])
    produto = SelectField('Produção', choices=[('ouro', 'Extração de Ouro'), ('ferro', 'Mineração de Ferro')], validators=[DataRequired()])

    
    taxa_lucro = FloatField('Taxa de Lucro (0.01 a 0.99)', validators=[DataRequired(), NumberRange(min=0.01, max=0.99)])
    dinheiro = FloatField('Caixa Atual', validators=[NumberRange(min=0)])
    
    submit = SubmitField('Salvar Alterações')

    def __init__(self, *args, **kwargs):
        super(CompanyEditForm, self).__init__(*args, **kwargs)
        from app.models import Jogador
        # Lista todos os jogadores para definir o proprietário
        # Adiciona uma opção de NULO (0) para empresas estatais
        self.proprietario_id.choices = [(0, 'Estatal/Nenhum')] + [(j.id, f'{j.id}: {j.username}') for j in Jogador.query.all()]