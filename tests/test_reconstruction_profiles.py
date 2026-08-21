from pathlib import Path

from app.core.services.reconstruction_profiles import ReconstructionTarget, classify_xml


def test_classifies_model3_naomi_and_mame(tmp_path: Path) -> None:
    xml = tmp_path / "test.xml"
    xml.write_text(
        "<mame>\n"
        "<machine name='daytona2' sourcefile='model3.cpp'><description>Daytona USA 2</description></machine>\n"
        "<machine name='ikaruga' sourcefile='naomi.cpp'><description>Ikaruga</description></machine>\n"
        "<machine name='pacman' sourcefile='pacman.cpp'><description>Pac-Man</description></machine>\n"
        "</mame>\n",
        encoding="utf-8",
    )
    result = classify_xml(xml)
    assert result["daytona2"] is ReconstructionTarget.SUPERMODEL3
    assert result["ikaruga"] is ReconstructionTarget.FLYCAST
    assert result["pacman"] is ReconstructionTarget.MAME
