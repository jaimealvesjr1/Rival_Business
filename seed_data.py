from app.__init__ import create_app
from app.models import db, Regiao, Item, RecursoRegional, Fabrica
from datetime import datetime, timedelta

# Inicialização do aplicativo
app = create_app()

def seed_regions():
    """Cria as 4 macroregiões iniciais de Minas Gerais com índices ajustados."""
    
    # Adicionamos a quarta localização e ajustamos os índices para ter uma coerência
    regioes_data = [
        {"nome": "Belo Horizonte", "desenvolvimento": 1.2, "educacao": 1.1, "saude": 1.15, "imposto_geral": 0.04}, # Alto índice de tudo, menor imposto
        {"nome": "Triângulo Mineiro", "desenvolvimento": 1.0, "educacao": 1.0, "saude": 1.0, "imposto_geral": 0.05}, # Índices medianos, imposto padrão
        {"nome": "Centro-Oeste de Minas", "desenvolvimento": 0.9, "educacao": 0.95, "saude": 0.9, "imposto_geral": 0.06}, # Índices um pouco abaixo, imposto maior
        {"nome": "Vale do Rio Doce", "desenvolvimento": 0.8, "educacao": 0.85, "saude": 0.8, "imposto_geral": 0.07}, # Índices menores, imposto mais alto
    ]
    
    for r_data in regioes_data:
        if not Regiao.query.filter_by(nome=r_data['nome']).first():
            regiao = Regiao(
                nome=r_data['nome'],
                indice_desenvolvimento=r_data['desenvolvimento'],
                indice_educacao=r_data['educacao'],
                indice_saude=r_data['saude'],
                taxa_imposto_geral=r_data['imposto_geral']
            )
            db.session.add(regiao)
    
    db.session.commit()
    print("Regiões iniciais criadas.")
    return Regiao.query.all()


def seed_items():
    """Cria os itens (matérias-primas, insumos e mercadorias) iniciais."""
    
    # Estrutura: {"nome": "", "tipo": "Materia-Prima/Insumo/Mercadoria", "preco_base": 0.0, "peso": 0.0}
    itens_data = [
        # Matérias-Primas
        {"nome": "Ouro Bruto", "tipo": "Materia-Prima", "preco_base": 5000.0, "peso": 0.1},
        {"nome": "Petróleo Bruto", "tipo": "Materia-Prima", "preco_base": 100.0, "peso": 5.0},
        {"nome": "Minério de Ferro", "tipo": "Materia-Prima", "preco_base": 80.0, "peso": 10.0},
        {"nome": "Madeira Bruta", "tipo": "Materia-Prima", "preco_base": 50.0, "peso": 8.0},
        
        # Insumos (Novos e ajustados)
        {"nome": "Plástico", "tipo": "Insumo", "preco_base": 300.0, "peso": 2.0},              # Derivado de Petróleo Bruto
        {"nome": "Bobina de Aço", "tipo": "Insumo", "preco_base": 450.0, "peso": 6.0},         # Derivado de Minério de Ferro
        {"nome": "Tábuas", "tipo": "Insumo", "preco_base": 150.0, "peso": 7.0},                # Derivado de Madeira Bruta
        {"nome": "Combustível", "tipo": "Insumo", "preco_base": 200.0, "peso": 4.0},           # Derivado de Petróleo Bruto
        {"nome": "Borracha", "tipo": "Insumo", "preco_base": 180.0, "peso": 3.0},              # Derivado de Madeira Bruta (látex)
        
        # Mercadorias (Produtos Finais)
        {"nome": "Móveis", "tipo": "Mercadoria", "preco_base": 1200.0, "peso": 30.0},
        {"nome": "Brinquedos", "tipo": "Mercadoria", "preco_base": 500.0, "peso": 1.5},
        {"nome": "Veículos", "tipo": "Mercadoria", "preco_base": 15000.0, "peso": 100.0},
    ]

    for i_data in itens_data:
        if not Item.query.filter_by(nome=i_data['nome']).first():
            # O uso de **i_data é uma forma limpa de passar todos os dados do dicionário
            item = Item(**i_data) 
            db.session.add(item)
    
    db.session.commit()
    print("Itens, insumos e mercadorias iniciais criados.")
    return Item.query.all()


def seed_resources_and_factories(regioes, itens):
    """Cria os limites de recursos regionais (4 tipos) e fábricas públicas de extração (4 tipos)."""
    
    # Para o RecursoRegional, usamos o 'tipo_recurso' (string), que está alinhado ao tipo de fábrica
    recursos_config = [
        {'tipo': 'Petróleo', 'limite': 50000.0, 'nome_fabrica': 'Poço de Petróleo'},
        {'tipo': 'Minério', 'limite': 80000.0, 'nome_fabrica': 'Mina de Ferro'},
        {'tipo': 'Ouro', 'limite': 1000.0, 'nome_fabrica': 'Mina de Ouro'},
        {'tipo': 'Madeira', 'limite': 60000.0, 'nome_fabrica': 'Área de Silvicultura'}, # Novo recurso
    ]

    for regiao in regioes:
        for config in recursos_config:
            # 1. Recursos Regionais (Limites de 12h)
            # Garantimos que o recurso exista na localização antes de adicioná-lo
            if not RecursoRegional.query.filter_by(regiao_id=regiao.id, tipo_recurso=config['tipo']).first():
                db.session.add(RecursoRegional(
                    regiao_id=regiao.id, 
                    tipo_recurso=config['tipo'], 
                    limite_total_12h=config['limite'], 
                    # Define a renovação para 12h no futuro
                    data_renovacao=datetime.utcnow() + timedelta(hours=12) 
                ))
                
            # 2. Fábricas Públicas (Propriedade Regional)
            # Garantimos que a fábrica de extração exista na localização
            if not Fabrica.query.filter_by(regiao_id=regiao.id, tipo='Publica', tipo_recurso_publico=config['tipo']).first():
                db.session.add(Fabrica(
                    regiao_id=regiao.id, 
                    tipo='Publica', 
                    tipo_recurso_publico=config['tipo'], 
                    nome=f'{config["nome_fabrica"]} {regiao.nome}', 
                    dono_id=None # Fábricas públicas não têm dono_id
                ))
            
    db.session.commit()
    print("Recursos Regionais (4 tipos) e Fábricas Públicas de extração (4 tipos) criados em todas as regiões.")


if __name__ == '__main__':
    # Usamos o 'app_context' para que o Flask e o SQLAlchemy funcionem corretamente
    with app.app_context(): 
        # A ordem é importante: Regiões e Itens primeiro, pois são usados para configurar Recursos e Fábricas
        regioes = seed_regions()
        itens = seed_items()
        seed_resources_and_factories(regioes, itens)
        print("\n--- DADOS INICIAIS SEMEADOS COM SUCESSO! ---")
