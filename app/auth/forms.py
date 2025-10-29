from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import Jogador

class RegistrationForm(FlaskForm):
    """Formulário para registro de novos jogadores."""
    username = StringField('Nome de Usuário', 
                           validators=[DataRequired(), Length(min=2, max=20)])
    
    password = PasswordField('Senha', validators=[DataRequired()])
    
    confirm_password = PasswordField('Confirmar Senha',
                                     validators=[DataRequired(), EqualTo('password', message='As senhas devem ser iguais.')])
    
    submit = SubmitField('Registrar')

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
