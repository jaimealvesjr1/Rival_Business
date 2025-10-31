def calculate_player_factors(jogador):
    """Calcula os fatores de bônus/desconto com base nas habilidades do jogador."""

    # SAÚDE: Desconto no Gasto de Energia (Max 80%)
    saude_level = jogador.habilidade_saude
    desconto_energia = min(0.80, saude_level * 0.01) 

    # EDUCAÇÃO: Bônus no Ganho de XP Geral (Max 80%)
    educacao_level = jogador.habilidade_educacao
    bonus_xp_geral = min(0.80, educacao_level * 0.01)

    # FILANTROPIA: Desconto no Imposto (Max 50%)
    filantropia_level = jogador.habilidade_filantropia
    desconto_imposto = min(0.50, filantropia_level * 0.01)

    return {
        'desconto_energia': desconto_energia,
        'multiplicador_xp_educacao': 1.0 + bonus_xp_geral,
        'desconto_imposto': desconto_imposto
    }
