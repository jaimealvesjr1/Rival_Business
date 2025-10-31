from flask import redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.skill_development import bp
from app.models import TreinamentoAtivo
from config import Config
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from config import Config

footer = {'ano': Config.ANO_ATUAL, 'versao': Config.VERSAO_APP}

@bp.route('/train/<skill_key>', methods=['POST'])
@login_required
def train_skill(skill_key):
    from app.models import Jogador
    jogador = Jogador.query.get(current_user.id)
    # Lista de habilidades válidas para garantir segurança
    valid_skills = ['educacao', 'filantropia', 'saude']
    
    if skill_key not in valid_skills:
        flash('Habilidade inválida!', 'danger')
        return redirect(url_for('profile.view_profile'))
    
    jogador = current_user
    
    # 1. Verificar se o jogador já está treinando
    if jogador.treino_ativo:
        if jogador.treino_ativo.habilidade.startswith('armazem_'):
             pass 
        else:
             flash(f"Você já está treinando {jogador.treino_ativo.habilidade.capitalize()}!", 'warning')
             return redirect(url_for('profile.view_profile'))
    
    if jogador.check_level_up():
        flash(f"PARABÉNS! Você alcançou o Nível {jogador.nivel}!", 'success')
        
    # 2. Obter o nível atual da habilidade
    skill_attr = f'habilidade_{skill_key}'
    current_level = getattr(jogador, skill_attr)
    
    # 3. Calcular custo e tempo para o próximo nível
    custo_info = jogador.get_skill_upgrade_info(skill_key)
    custo_money = custo_info['money']
    custo_gold = custo_info['gold']
    tempo_minutos = custo_info['time']
    
    # 4. Verificar se o jogador tem dinheiro suficiente
    if jogador.dinheiro < custo_money or jogador.gold < custo_gold:
        custo_money_formatado = f"R$ {custo_money:,.0f}".replace(",", ".")
        flash(f"Você não tem fundos. Requer {custo_money_formatado} e G{custo_gold:.2f}.", 'danger')
        return redirect(url_for('profile.view_profile'))

    try:
        # 5. Subtrair o custo e iniciar o Treino
        jogador.dinheiro -= custo_money
        jogador.gold -= custo_gold
        
        data_fim = datetime.utcnow() + timedelta(minutes=tempo_minutos)
        
        treino = TreinamentoAtivo(
            jogador_id=jogador.id,
            habilidade=skill_key,
            nivel_alvo=current_level + 1.0, # Nível alvo é o nível atual + 1
            data_fim=data_fim
        )
        
        db.session.add(treino)
        db.session.commit()
        
        flash(f"Treinamento de {skill_key.capitalize()} iniciado! Ficará pronto em {tempo_minutos} minutos.", 'success')
        
    except IntegrityError:
        db.session.rollback()
        flash('Você já tem um treino ativo e só pode treinar uma habilidade por vez!', 'warning')
    
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao iniciar treino: {e}", 'danger')
        
    return redirect(url_for('profile.view_profile'))
