from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

class OpenCompanyForm(FlaskForm):
    """Formulário para o jogador definir o nome e a taxa de lucro da nova empresa."""
    
    # Validação do Nome
    nome = StringField('Nome da Empresa', validators=[
        DataRequired(), 
        Length(min=3, max=50, message='O nome deve ter entre 3 e 50 caracteres.')
    ])
    
    # Validação da Taxa de Lucro
    # A taxa de lucro deve ser definida pelo jogador (Ex: 0.05 = 5%)
    taxa_lucro = FloatField('Taxa de Lucro (Ex: 0.15 para 15%)', 
                            default=0.15,
                            validators=[
                                DataRequired(),
                                NumberRange(min=0.01, max=0.99, message='A taxa deve ser entre 0.01 e 0.99.')
                            ])
                            
    submit = SubmitField('Confirmar Abertura')
