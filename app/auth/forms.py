from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import Jogador, Regiao

class RegistrationForm(FlaskForm):
    """Formulário para registro de novos jogadores."""
    username = StringField('Nome de Usuário', 
                           validators=[DataRequired(), Length(min=2, max=20)])
    
    password = PasswordField('Senha', validators=[DataRequired()])
    
    confirm_password = PasswordField('Confirmar Senha',
                                     validators=[DataRequired(), EqualTo('password', message='As senhas devem ser iguais.')])
    
    regiao_inicial_id = SelectField('Região Inicial', 
                                    coerce=int, # Garante que o valor retornado seja um inteiro
                                    validators=[DataRequired(message='Selecione uma região.')])
    
    submit = SubmitField('Registrar')

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.regiao_inicial_id.choices = [(r.id, r.nome) for r in Regiao.query.order_by(Regiao.nome).all()]
        
        if not self.regiao_inicial_id.choices:
             self.regiao_inicial_id.choices = [(-1, 'Nenhuma Região Disponível')]

    def validate_username(self, username):
        """Verifica se o nome de usuário já está em uso."""
        jogador = Jogador.query.filter_by(username=username.data).first()
        if jogador:
            raise ValidationError('Este nome de usuário já está em uso. Escolha outro.')

class LoginForm(FlaskForm):
    """Formulário para login de jogadores."""
    username = StringField('Nome de Usuário', 
                           validators=[DataRequired()])
    
    password = PasswordField('Senha', validators=[DataRequired()])
    
    remember = BooleanField('Lembrar-me')
    
    submit = SubmitField('Entrar')
