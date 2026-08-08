"""
Perfis pré‑definidos para seleção rápida.
"""

from ..domain.set_profile import SetProfile, EmulationStatus, SetType

def arcade_only() -> SetProfile:
    """Perfil: somente Arcade, sem clones, status PRELIMINARY."""
    return SetProfile(
        name="Arcade Only",
        categories=["Arcade"],
        emulation_status=EmulationStatus.PRELIMINARY,
        set_type=SetType.SPLIT,
        include_clones=False,
        keep_bios=True,
        keep_devices=True,
        keep_samples=False,
        keep_chds=True,
    )

def all_systems() -> SetProfile:
    """Perfil: todos os sistemas, sem filtros de categoria."""
    return SetProfile(
        name="All Systems",
        categories=[],  # vazio = todas
        emulation_status=EmulationStatus.ALL,
        set_type=SetType.SPLIT,
        include_clones=True,
        keep_bios=True,
        keep_devices=True,
        keep_samples=True,
        keep_chds=True,
    )

def consoles_only() -> SetProfile:
    """Perfil: apenas consoles e portáteis."""
    return SetProfile(
        name="Consoles & Portables",
        categories=["Console", "Portable"],
        emulation_status=EmulationStatus.PRELIMINARY,
        set_type=SetType.SPLIT,
        include_clones=True,
        keep_bios=True,
        keep_devices=True,
        keep_samples=False,
        keep_chds=False,
    )

def computers_only() -> SetProfile:
    """Perfil: apenas computadores."""
    return SetProfile(
        name="Computers Only",
        categories=["Computer"],
        emulation_status=EmulationStatus.PRELIMINARY,
        set_type=SetType.SPLIT,
        include_clones=True,
        keep_bios=True,
        keep_devices=True,
        keep_samples=False,
        keep_chds=False,
    )

def mechanical_only() -> SetProfile:
    """Perfil: apenas máquinas mecânicas (pinball, frutas, etc.)."""
    return SetProfile(
        name="Mechanical",
        categories=["Pinball", "Fruit Machine", "Casino", "Gambling", "Quiz", "Mahjong", "Tabletop", "Electromechanical", "Mechanical"],
        emulation_status=EmulationStatus.ALL,
        set_type=SetType.SPLIT,
        include_clones=True,
        keep_bios=False,
        keep_devices=False,
        keep_samples=False,
        keep_chds=False,
    )