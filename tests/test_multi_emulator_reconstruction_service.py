from app.core.services.multi_emulator_reconstruction_service import (
    MultiEmulatorReconstructionService,
)
from app.core.services.reconstruction_profiles import ReconstructionTarget
from app.mame.reconstruction_engine import ReconstructionMachine


def test_game_group_keeps_support_machines_out() -> None:
    machines = [
        ReconstructionMachine("pacman"),
        ReconstructionMachine("daytona2"),
        ReconstructionMachine("ikaruga"),
        ReconstructionMachine("neogeo"),
        ReconstructionMachine("z80"),
    ]
    classification = {
        "pacman": ReconstructionTarget.MAME,
        "daytona2": ReconstructionTarget.SUPERMODEL3,
        "ikaruga": ReconstructionTarget.FLYCAST,
        "neogeo": ReconstructionTarget.MAME,
        "z80": ReconstructionTarget.MAME,
    }
    groups = MultiEmulatorReconstructionService._build_game_groups(
        machines,
        classification,
        {"neogeo", "z80"},
    )
    assert [m.name for m in groups[ReconstructionTarget.MAME]] == ["pacman"]
    assert [m.name for m in groups[ReconstructionTarget.SUPERMODEL3]] == ["daytona2"]
    assert [m.name for m in groups[ReconstructionTarget.FLYCAST]] == ["ikaruga"]
