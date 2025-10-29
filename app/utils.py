from math import radians, sin, cos, sqrt, atan2
import locale

def format_currency_python(value, prefix='R$', separator='.'):
    """Formata valores de dinheiro (R$ e $) no formato X.XXX (sem centavos) para uso em Python."""
    valor_arredondado = int(round(value))
    valor_formatado = f"{valor_arredondado:,}".replace(',', separator)
    return f"{prefix} {valor_formatado}"

def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Calcula a distância (em KM) entre dois pontos usando Haversine."""
    R = 6371.0 
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return round(distance, 2)
