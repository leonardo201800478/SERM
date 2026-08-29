"""Mapeamento de categorias granulares (catver.ini / seed) para macro-grupos.

Facilita a filtragem em massa: em vez de marcar dezenas de categorias
individualmente, o usuário exclui/inclui um "macro grupo" inteiro (ex.:
"System / Non-Games") e todas as categorias que pertencem a ele são
afetadas de uma vez.

As chaves usam a mesma normalização aplicada em
``FilterService.import_categories_from_catver`` / ``seed_default_categories``
(minúsculas, espaços viram '_', caracteres especiais removidos), então o
mapeamento casa diretamente com ``category.name`` no banco.

Este módulo não conhece SQLite nem GUI: é uma tabela de dados pura, para
poder ser testada isoladamente e reaproveitada tanto pelo ``FilterService``
quanto por qualquer outra camada (relatórios, exportação, etc.).
"""

from __future__ import annotations

# ============================================================================
# MAPEAMENTO PRINCIPAL
# ============================================================================
#
# Chave:   nome normalizado da categoria (igual a ``category.name`` no banco)
# Valor:   nome do macro-grupo exibido na GUI
#
MACRO_CATEGORIES_MAPPING: dict[str, str] = {
    # 1. Luta / Briga de Rua
    "fighter": "Fighter / Beat 'em Up",

    # 2. Tiro
    "shooter": "Shooter / Shmup",

    # 3. Plataforma e Labirinto
    "platform": "Platform / Action",
    "maze": "Platform / Action",
    "climbing": "Platform / Action",

    # 4. Corrida e Pilotagem
    "driving": "Driving / Racing",

    # 5. Esportes
    "sports": "Sports / Games",

    # 6. Quebra-Cabeça e Tabuleiro
    "puzzle": "Puzzle / Tabletop",
    "ball_paddle": "Puzzle / Tabletop",
    "board_game": "Puzzle / Tabletop",
    "tabletop": "Puzzle / Tabletop",
    "card_games": "Puzzle / Tabletop",

    # 7. Ritmo e Música
    "music_game": "Music / Rhythm",
    "musical_instrument": "Music / Rhythm",
    "musical_instrument_accessory": "Music / Rhythm",
    "music_player": "Music / Rhythm",

    # 8. Cassino / Azar e Fliperama Mecânico
    "slot_machine": "Casino / Gambling / Pinball",
    "gambling": "Casino / Gambling / Pinball",
    "casino": "Casino / Gambling / Pinball",
    "electromechanical": "Casino / Gambling / Pinball",
    "redemption_game": "Casino / Gambling / Pinball",
    "arcade": "Casino / Gambling / Pinball",

    # 9. Sistemas, Computadores e BIOS (geralmente ocultados)
    "system": "System / Non-Games",
    "game_console": "System / Non-Games",
    "computer": "System / Non-Games",
    "utilities": "System / Non-Games",
    "calculator": "System / Non-Games",
    "misc": "System / Non-Games",
    "handheld": "System / Non-Games",
}

# Categorias existentes no banco (vindas do seed padrão ou de um
# catver.ini importado) que não constam explicitamente no mapeamento acima
# caem neste grupo — nunca são descartadas ou escondidas silenciosamente.
UNCLASSIFIED_MACRO: str = "Outras / Não Classificadas"

# Ordem de exibição dos macro-grupos na GUI. Qualquer macro-grupo que não
# apareça aqui (não deveria acontecer, mas por segurança) vai para o final.
MACRO_CATEGORY_ORDER: list[str] = [
    "Fighter / Beat 'em Up",
    "Shooter / Shmup",
    "Platform / Action",
    "Driving / Racing",
    "Sports / Games",
    "Puzzle / Tabletop",
    "Music / Rhythm",
    "Casino / Gambling / Pinball",
    "System / Non-Games",
    UNCLASSIFIED_MACRO,
]


def get_macro_category(category_name: str) -> str:
    """Retorna o macro-grupo de uma categoria já normalizada.

    Args:
        category_name: valor de ``category.name`` no banco (normalizado:
            minúsculas, espaços viram '_', sem caracteres especiais).

    Returns:
        Nome do macro-grupo correspondente, ou ``UNCLASSIFIED_MACRO``
        quando a categoria não está mapeada.
    """
    if not category_name:
        return UNCLASSIFIED_MACRO
    return MACRO_CATEGORIES_MAPPING.get(category_name.strip().lower(), UNCLASSIFIED_MACRO)


def macro_sort_key(macro_name: str) -> int:
    """Chave de ordenação para exibir os macro-grupos numa ordem estável.

    Grupos conhecidos aparecem na ordem definida em
    ``MACRO_CATEGORY_ORDER``; qualquer nome desconhecido vai para o final.
    """
    try:
        return MACRO_CATEGORY_ORDER.index(macro_name)
    except ValueError:
        return len(MACRO_CATEGORY_ORDER)


def get_categories_for_macro(macro_name: str) -> list[str]:
    """Retorna todas as categorias (chaves) que pertencem a um macro-grupo.

    Útil para aplicar/desfazer exclusão em lote sem precisar consultar
    o banco: dado o nome de um macro-grupo, devolve a lista de nomes de
    categoria normalizados que pertencem a ele, segundo o mapeamento
    estático. Note que isso reflete apenas o mapeamento conhecido — para
    saber quais dessas categorias realmente existem no banco (com
    contagem de máquinas), use ``FilterService.get_macro_categories_with_counts``.
    """
    return [
        name
        for name, macro in MACRO_CATEGORIES_MAPPING.items()
        if macro == macro_name
    ]
