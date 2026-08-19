"""Integrações e compatibilidade do pacote MAME Set Builder.

A validação de CHD é delegada ao chdman distribuído pelo próprio MAME. Os
patches abaixo preservam a API existente de PhysicalRomScanner e
ReconstructionEngine enquanto substituem apenas a validação incorreta de
SHA-1 bruto do arquivo .chd pelo digest lógico validado pelo chdman.
"""
from __future__ import annotations

import shutil

from .chdman_validator import ChdmanError, validate_chd


def _patch_chd_validation() -> None:
    """Aplica a integração chdman às classes já existentes sem quebrar a API."""
    from .physical_rom_scanner import PhysicalRomScanner
    from .reconstruction_engine import ReconstructionEngine

    def scan_expected_chd(self, machine_name: str, disk: dict, cancelled=None) -> dict:
        """Localiza e valida um CHD usando chdman verify/info."""
        disk_name = str(disk.get("name") or "").strip()
        expected_sha1 = str(disk.get("sha1") or "").strip().lower()
        expected_logical_size = int(disk.get("size") or 0)
        if not disk_name:
            return {"status": "error", "source_path": None, "actual_size": 0, "actual_sha1": None, "error": "CHD sem nome"}

        disk_filename = disk_name if disk_name.lower().endswith(".chd") else f"{disk_name}.chd"
        candidates = []
        for base in self.source_dirs:
            for candidate_machine in [machine_name, *(disk.get("_parent_machines") or [])]:
                if candidate_machine:
                    candidates.append(base / candidate_machine / disk_filename)
            candidates.append(base / disk_filename)

        found = next((path for path in candidates if path.is_file()), None)
        if found is None:
            return {
                "status": "missing",
                "source_path": None,
                "actual_size": 0,
                "actual_sha1": None,
                "logical_size": 0,
                "error": "CHD não encontrado",
            }

        try:
            self._check_cancelled(cancelled)
            valid, info = validate_chd(
                found,
                expected_sha1=expected_sha1 or None,
                expected_logical_size=expected_logical_size,
            )
            return {
                "status": "valid" if valid else "invalid",
                "source_path": str(found),
                "actual_size": int(info.get("physical_size") or found.stat().st_size),
                "actual_sha1": str(info.get("sha1") or "").lower() or None,
                "logical_size": int(info.get("logical_size") or 0),
                "chd_version": info.get("chd_version"),
                "chdman_version": info.get("chdman_version"),
                "chdman_verified": bool(info.get("verified")),
                "error": None if valid else (
                    "SHA-1 lógico incompatível"
                    if not info.get("sha1_match", True)
                    else "tamanho lógico incompatível"
                ),
            }
        except ChdmanError as exc:
            return {
                "status": "error",
                "source_path": str(found),
                "actual_size": found.stat().st_size if found.exists() else 0,
                "actual_sha1": None,
                "logical_size": 0,
                "chdman_verified": False,
                "error": str(exc),
            }
        except Exception as exc:
            return {
                "status": "error",
                "source_path": str(found),
                "actual_size": found.stat().st_size if found.exists() else 0,
                "actual_sha1": None,
                "logical_size": 0,
                "chdman_verified": False,
                "error": str(exc),
            }

    def stream_source(self, item, source, staged) -> None:
        """Mantém o streaming original para ROMs e usa chdman para CHDs."""
        if not item.is_chd:
            return original_stream_source(self, item, source, staged)

        kind, source_path, member = source
        if kind != "chd":
            raise ValueError(f"origem inválida para CHD: {kind}")
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, staged)
        expected_size = 0
        try:
            valid, info = validate_chd(
                staged,
                expected_sha1=item.chd_sha1,
                expected_logical_size=expected_size,
            )
        except ChdmanError:
            staged.unlink(missing_ok=True)
            raise
        if not valid:
            staged.unlink(missing_ok=True)
            if not info.get("sha1_match", True):
                raise ValueError(
                    f"SHA-1 lógico do CHD incompatível: esperado={item.chd_sha1}, encontrado={info.get('sha1')}"
                )
            raise ValueError("CHD inválido segundo chdman")

    def validate_existing_chd(target, chd) -> bool:
        """Valida CHD publicado usando chdman, inclusive o digest lógico."""
        if not target.is_file():
            return False
        try:
            valid, _info = validate_chd(
                target,
                expected_sha1=chd.chd_sha1,
                expected_logical_size=0,
            )
            return valid
        except (ChdmanError, OSError, ValueError):
            return False

    original_stream_source = ReconstructionEngine._stream_source
    PhysicalRomScanner._scan_expected_chd = scan_expected_chd
    ReconstructionEngine._stream_source = stream_source
    ReconstructionEngine._validate_existing_chd = staticmethod(validate_existing_chd)


_patch_chd_validation()

__all__ = ["ChdmanError", "validate_chd"]
