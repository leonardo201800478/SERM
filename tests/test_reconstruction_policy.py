from app.core.services.reconstruction_policy import (
    MameDumpStatus,
    ReconstructionAction,
    classify_rom,
)


def test_good_rom_is_kept():
    decision = classify_rom(physical_status="valid", expected_size=10, actual_size=10, expected_crc="12345678", actual_crc="12345678", mame_status="good")
    assert decision.dump_status is MameDumpStatus.GOOD
    assert decision.action is ReconstructionAction.KEEP
    assert decision.executable is True
    assert decision.blocking is False


def test_known_bad_dump_is_usable_when_matching():
    decision = classify_rom(physical_status="valid", expected_size=10, actual_size=10, expected_crc="12345678", actual_crc="12345678", mame_status="baddump")
    assert decision.dump_status is MameDumpStatus.BAD_DUMP
    assert decision.action is ReconstructionAction.KEEP
    assert decision.executable is True
    assert "BAD DUMP" in decision.reason


def test_nodump_missing_does_not_block():
    decision = classify_rom(physical_status="missing", mame_status="nodump")
    assert decision.dump_status is MameDumpStatus.NO_DUMP
    assert decision.action is ReconstructionAction.IGNORE
    assert decision.executable is True
    assert decision.blocking is False


def test_optional_missing_does_not_block():
    decision = classify_rom(physical_status="missing", mame_status="good", optional=True)
    assert decision.action is ReconstructionAction.IGNORE
    assert decision.executable is True
    assert decision.blocking is False


def test_invalid_crc_has_exact_reason():
    decision = classify_rom(physical_status="invalid", expected_size=100, actual_size=100, expected_crc="aaaaaaaa", actual_crc="bbbbbbbb", mame_status="good")
    assert decision.action is ReconstructionAction.SEARCH
    assert decision.blocking is True
    assert "CRC esperado aaaaaaaa, encontrado bbbbbbbb" in decision.reason
