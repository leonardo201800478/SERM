"""MAME DAT/ListXML extraction through the official MAME executable.

The MAME executable is the authoritative producer for this source. SERM invokes
``mame -listxml`` instead of downloading or maintaining a parallel DAT.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


class MameDatError(RuntimeError):
    """Raised when MAME DAT/ListXML extraction fails."""


@dataclass(frozen=True, slots=True)
class MameDat:
    """Result of a MAME ``-listxml`` extraction."""

    executable: Path
    xml_text: str
    machine_count: int

    def write(self, destination: Path) -> Path:
        """Persist the extracted XML and return the destination path."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.xml_text, encoding="utf-8", newline="\n")
        return destination


def scrape_mame_dat(
    executable: str | Path,
    *,
    timeout: float = 120.0,
) -> MameDat:
    """Run the installed MAME executable with ``-listxml`` and parse its DAT.

    Parameters
    ----------
    executable:
        Path to the MAME executable (normally ``mame.exe`` on Windows).
    timeout:
        Maximum number of seconds allowed for the command.

    Returns
    -------
    MameDat
        Raw XML plus the number of ``<machine>`` entries found.

    Raises
    ------
    MameDatError
        If the executable is missing, the process fails, times out, or emits
        invalid XML.
    """
    executable_path = Path(executable).expanduser().resolve()
    if not executable_path.is_file():
        raise MameDatError(f"MAME executable not found: {executable_path}")

    try:
        completed = subprocess.run(
            [str(executable_path), "-listxml"],
            cwd=executable_path.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except OSError as exc:
        raise MameDatError(f"Unable to execute MAME: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MameDatError(f"MAME -listxml timed out after {timeout:g}s") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        detail = f": {stderr}" if stderr else ""
        raise MameDatError(
            f"MAME -listxml failed with exit code {completed.returncode}{detail}"
        )

    xml_text = completed.stdout
    if not xml_text.strip():
        raise MameDatError("MAME -listxml returned an empty document")

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise MameDatError("MAME -listxml returned invalid XML") from exc

    machine_count = sum(1 for element in root if element.tag == "machine")
    return MameDat(
        executable=executable_path,
        xml_text=xml_text,
        machine_count=machine_count,
    )


__all__ = ["MameDat", "MameDatError", "scrape_mame_dat"]
