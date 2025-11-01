from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField, SelectField
from wtforms.validators import DataRequired, NumberRange

class MarketOrderForm(FlaskForm):
    """Formulário genérico para criar uma ordem de Venda ou Compra."""
    
    # Lista de recursos que podem ser negociados
    # (Pode ser populada dinamicamente no futuro, por enquanto 'gold' e 'ferro')
    resource_type = SelectField('Recurso', choices=[
        ('gold', 'Gold (Kg)'),
        ('ferro', 'Ferro (ton)'),
    ], validators=[DataRequired()])

    quantity = FloatField('Quantidade', validators=[
        DataRequired(), 
        NumberRange(min=1, message="A quantidade deve ser de pelo menos 1.")
    ])
    
    price_per_unit = FloatField('Preço por Unidade (R$)', validators=[
        DataRequired(),
        NumberRange(min=1, message="O preço deve ser de pelo menos R$ 1.")
    ])
    
    submit_sell = SubmitField('Criar Ordem de Venda')
    submit_buy = SubmitField('Criar Ordem de Compra')