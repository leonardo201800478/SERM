"""
Regras de classificação para MAME – versão consolidada e validada.
Arcade é definido por exclusão, garantindo cobertura máxima.
"""

from typing import Dict, Any, Callable, List, Tuple

Rule = Callable[[Dict[str, Any]], bool]

# =======================================================================
# PALAVRAS-CHAVE POR CATEGORIA (validadas e expandidas)
# =======================================================================

PINBALL_KEYWORDS = [
    "pinball", "pin-ball", "flipper", "bumper", "tilt", "drain",
    "silverball", "slingshot", "pop bumper", "drop target", "spinner",
    "solenoid", "score reel", "bally", "williams", "stern", "gottlieb",
    "data east pinball", "capcom pinball", "zaccaria", "playmatic",
    "bell fruit", "pinmame", "vpinmame"
]

FRUIT_MACHINE_KEYWORDS = [
    "fruit machine", "slot machine", "one-armed bandit", "jackpot",
    "cherry", "bell", "bar", "seven", "fruit", "bandit", "puggy",
    "profit", "payout", "coin drop", "hopper", "nudge", "hold",
    "gamble feature", "skill stop", "jpm", "barcrest", "bellfruit",
    "maygay", "mazooma", "project coin"
]

CASINO_KEYWORDS = [
    "casino", "roulette", "blackjack", "craps", "keno", "baccarat",
    "sic bo", "fan tan", "pai gow", "big wheel", "wheel of fortune",
    "casino game", "table game", "chinese casino", "macau",
    "carnival game", "mini-game", "casino royale"
]

GAMBLING_KEYWORDS = [
    "gambling", "poker", "video poker", "joker", "draw poker",
    "stud poker", "wild card", "bet", "wager", "gamble", "stake",
    "high card", "flush", "straight", "full house", "royal flush",
    "jackpot poker", "deuces wild", "tens or better", "caribbean stud"
]

QUIZ_KEYWORDS = [
    "quiz", "trivia", "question", "answer", "knowledge",
    "who wants to be", "millionaire", "jeopardy", "quiz show",
    "game show", "test your knowledge", "brain game", "trivia game",
    "family feud", "password", "pyramid", "lucky letters"
]

MAHJONG_KEYWORDS = [
    "mahjong", "mahjongg", "mj", "tile", "dragon", "wind", "bamboo",
    "character", "flower", "season", "riichi", "hong kong mahjong",
    "taiwanese mahjong", "japanese mahjong", "shanghai mahjong",
    "mahjong solitaire", "tile matching"
]

TABLETOP_KEYWORDS = [
    "tabletop", "table-top", "countertop", "cocktail", "bartop",
    "sit-down", "table", "counter", "tabletop arcade", "coffee table",
    "bar top"
]

ELECTROMECHANICAL_KEYWORDS = [
    "electromechanical", "em", "relay", "stepper", "score motor",
    "bingo", "bally bingo", "chicago coin", "electro-mechanical",
    "motor driven", "mechanical reels", "stepper unit",
    "score reel", "chime", "bell", "coin mechanism"
]

CONSOLE_KEYWORDS = [
    "nintendo", "nes", "famicom", "super nintendo", "snes", "n64",
    "gamecube", "wii", "wii u", "switch", "game boy", "gameboy",
    "virtual boy", "pokemon mini", "game & watch", "g&w",
    "sega", "master system", "megadrive", "genesis", "saturn",
    "dreamcast", "gamegear", "nomad", "sega cd", "32x", "mega cd",
    "sony", "playstation", "psx", "ps2", "ps3", "psp", "vita",
    "xbox", "xbox 360", "xbox one", "xbox series",
    "atari 2600", "atari 5200", "atari 7800", "atari jaguar",
    "atari lynx", "atari xegs", "atari 400", "atari 800",
    "coleco", "intellivision", "odyssey", "vectrex", "pong",
    "neo geo", "neo-geo", "cd-i", "3do", "jaguar", "turbo",
    "pc engine", "amiga cd32", "fm towns marty", "apple pippin",
    "gizmondo", "n-gage", "wonderswan", "game.com", "gp32",
    "tapwave", "ouya", "leapster", "didj", "pocketstation",
    "vm lab", "casio loopy", "nuon", "cd32", "cdtv", "laseractive"
]

COMPUTER_KEYWORDS = [
    "apple", "macintosh", "mac", "apple ii", "apple iie", "apple iic",
    "apple iigs", "apple iii", "power mac", "imac", "lisa",
    "ibm", "pc", "pc/xt", "pc/at", "dos", "windows", "ms-dos",
    "thinkpad", "ps/2", "microchannel",
    "commodore", "c64", "c128", "vic-20", "plus/4", "pet", "amiga",
    "amiga cd", "amiga 500", "amiga 600", "amiga 1200", "amiga 4000",
    "atari st", "atari tt", "atari falcon", "atari 400", "atari 800",
    "msx", "msx2", "spectrum", "zx spectrum", "sinclair",
    "bbc", "acorn", "archimedes", "amstrad", "cpc", "z80",
    "trs-80", "ti-99", "osborne", "xerox", "hp", "sharp",
    "x68000", "fm-towns", "pc-98", "pc88", "x1", "fujitsu fm",
    "microcomputer", "personal computer", "home computer",
    "desktop", "laptop", "notebook", "workstation", "server"
]

PORTABLE_KEYWORDS = [
    "game boy", "gameboy", "gamegear", "lynx", "nomad", "turboexpress",
    "neo geo pocket", "wonderswan", "game.com", "gp32", "n-gage",
    "psp", "vita", "switch lite", "ds", "3ds", "dsi", "2ds",
    "game & watch", "g&w", "microvision", "entex", "tomy", "vtech",
    "portable", "handheld", "pocket", "palmtop", "pda", "smartphone"
]

# =======================================================================
# REGRAS AUXILIARES
# =======================================================================

def _check_keywords(data: Dict[str, Any], keywords: List[str]) -> bool:
    text = (data.get("description", "") + " " + data.get("name", "")).lower()
    source = data.get("sourcefile", "").lower()
    return any(kw in text for kw in keywords) or any(kw in source for kw in keywords)

def _sourcefile_contains(data: Dict[str, Any], path: str) -> bool:
    source = data.get("sourcefile", "").lower()
    return path in source

# =======================================================================
# REGRAS BÁSICAS (atributos nativos)
# =======================================================================

def rule_is_bios(data: Dict[str, Any]) -> bool:
    return data.get("isbios", False)

def rule_is_device(data: Dict[str, Any]) -> bool:
    return data.get("isdevice", False)

def rule_runnable(data: Dict[str, Any]) -> bool:
    return data.get("runnable", True)

def rule_is_mechanical_attr(data: Dict[str, Any]) -> bool:
    return data.get("ismechanical", False)

# =======================================================================
# REGRAS ESPECÍFICAS
# =======================================================================

def rule_is_pinball(data: Dict[str, Any]) -> bool:
    return _check_keywords(data, PINBALL_KEYWORDS) or _sourcefile_contains(data, "pinball")

def rule_is_fruit_machine(data: Dict[str, Any]) -> bool:
    return _check_keywords(data, FRUIT_MACHINE_KEYWORDS) or _sourcefile_contains(data, "fruit")

def rule_is_casino(data: Dict[str, Any]) -> bool:
    return _check_keywords(data, CASINO_KEYWORDS)

def rule_is_gambling(data: Dict[str, Any]) -> bool:
    return _check_keywords(data, GAMBLING_KEYWORDS)

def rule_is_quiz(data: Dict[str, Any]) -> bool:
    return _check_keywords(data, QUIZ_KEYWORDS) or _sourcefile_contains(data, "quiz")

def rule_is_mahjong(data: Dict[str, Any]) -> bool:
    return _check_keywords(data, MAHJONG_KEYWORDS) or _sourcefile_contains(data, "mahjong")

def rule_is_tabletop(data: Dict[str, Any]) -> bool:
    return _check_keywords(data, TABLETOP_KEYWORDS)

def rule_is_electromechanical(data: Dict[str, Any]) -> bool:
    return _check_keywords(data, ELECTROMECHANICAL_KEYWORDS) or _sourcefile_contains(data, "em")

def rule_is_console(data: Dict[str, Any]) -> bool:
    return _check_keywords(data, CONSOLE_KEYWORDS) or _sourcefile_contains(data, "console")

def rule_is_computer(data: Dict[str, Any]) -> bool:
    return _check_keywords(data, COMPUTER_KEYWORDS) or _sourcefile_contains(data, "computer")

def rule_is_portable(data: Dict[str, Any]) -> bool:
    return _check_keywords(data, PORTABLE_KEYWORDS) or _sourcefile_contains(data, "handheld")

def rule_is_mechanical_fallback(data: Dict[str, Any]) -> bool:
    """Catch-all para ismechanical que não foi capturado pelas específicas."""
    if data.get("ismechanical") and not data.get("isbios") and not data.get("isdevice"):
        return True
    return False

# =======================================================================
# ARCADE POR EXCLUSÃO (sem exigência de sourcefile)
# =======================================================================

def rule_is_arcade(data: Dict[str, Any]) -> bool:
    # Exclui BIOS, Device, não-runnable
    if data.get("isbios") or data.get("isdevice"):
        return False
    if not data.get("runnable"):
        return False
    # Se for ismechanical, não é arcade (já foi ou será capturado pelo fallback)
    if data.get("ismechanical"):
        return False
    # Verifica se não se encaixa em nenhuma categoria específica
    if (rule_is_pinball(data) or rule_is_fruit_machine(data) or
        rule_is_casino(data) or rule_is_gambling(data) or rule_is_quiz(data) or
        rule_is_mahjong(data) or rule_is_tabletop(data) or rule_is_electromechanical(data) or
        rule_is_console(data) or rule_is_computer(data) or rule_is_portable(data)):
        return False
    # Se chegou até aqui, é Arcade
    return True

def rule_other(data: Dict[str, Any]) -> bool:
    return True

# =======================================================================
# ORDEM DE PRIORIDADE (a primeira que bater, classifica)
# =======================================================================

CATEGORIES: List[Tuple[str, List[Rule]]] = [
    ("BIOS", [rule_is_bios]),
    ("Device", [rule_is_device]),
    ("Pinball", [rule_is_pinball]),
    ("Fruit Machine", [rule_is_fruit_machine]),
    ("Casino", [rule_is_casino]),
    ("Gambling", [rule_is_gambling]),
    ("Quiz", [rule_is_quiz]),
    ("Mahjong", [rule_is_mahjong]),
    ("Tabletop", [rule_is_tabletop]),
    ("Electromechanical", [rule_is_electromechanical]),
    ("Portable", [rule_is_portable]),
    ("Console", [rule_is_console]),
    ("Computer", [rule_is_computer]),
    ("Mechanical", [rule_is_mechanical_fallback]),  # ismechanical não capturado
    ("Arcade", [rule_is_arcade]),                  # restante runnable não específico
    ("Other", [rule_other]),                       # catch-all final
]