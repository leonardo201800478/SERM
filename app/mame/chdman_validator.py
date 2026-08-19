"""Integração oficial com o ``chdman.exe`` distribuído pelo MAME.

CHDs não devem ser validados calculando SHA-1 sobre os bytes do arquivo .chd.
O digest de conteúdo esperado pelo MAME é o digest lógico armazenado no CHD.
Este módulo usa o próprio chdman para validar a integridade e obter esse
SHA-1, evitando duplicar a implementação do formato CHD no projeto.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


class ChdmanError(RuntimeError):
    """Erro ao localizar ou executar o chdman."""


_SHA1_RE = re.compile(r"^\s*SHA1:\s*([0-9a-f]{40})\s*$", re.IGNORECASE | re.MULTILINE)
_LOGICAL_SIZE_RE = re.compile(r"^\s*Logical size:\s*([0-9,]+)", re.IGNORECASE | re.MULTILINE)
_VERSION_RE = re.compile(r"chdman\s+.*?\b(\d+\.\d+)\b", re.IGNORECASE)


def find_chdman(explicit: str | Path | None = None) -> Path | None:
    """Localiza chdman usando configuração explícita, variáveis de ambiente ou PATH."""
    candidates: list[Path] = []

    if explicit:
        candidates.append(Path(explicit).expanduser())

    for variable in ("MAME_CHDMAN", "CHDMAN_EXE"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value).expanduser())

    exe_dir = os.environ.get("MAME_EXE_DIR")
    if exe_dir:
        candidates.append(Path(exe_dir).expanduser() / "chdman.exe")
        candidates.append(Path(exe_dir).expanduser() / "chdman")

    mame_exe = os.environ.get("MAME_EXECUTABLE") or os.environ.get("MAME_EXE")
    if mame_exe:
        mame_path = Path(mame_exe).expanduser()
        candidates.extend((mame_path.parent / "chdman.exe", mame_path.parent / "chdman"))
        candidates.extend((mame_path.parent / "exe" / "chdman.exe", mame_path.parent / "exe" / "chdman"))

    for name in ("chdman.exe", "chdman"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_file():
            return resolved
    return None


def _run(executable: Path, args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    """Executa chdman sem shell e retorna stdout/stderr em texto."""
    try:
        return subprocess.run(
            [str(executable), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ChdmanError(f"chdman não encontrado: {executable}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ChdmanError(f"chdman excedeu o timeout de {timeout}s: {executable}") from exc
    except OSError as exc:
        raise ChdmanError(f"falha ao executar chdman: {exc}") from exc


def chdman_info(path: str | Path, chdman_path: str | Path | None = None, timeout: int = 120) -> dict[str, Any]:
    """Obtém informações do CHD com ``chdman info -i``."""
    executable = find_chdman(chdman_path)
    if executable is None:
        raise ChdmanError(
            "chdman.exe não foi encontrado. Configure MAME_CHDMAN, MAME_EXE_DIR "
            "ou MAME_EXECUTABLE, ou coloque chdman no PATH."
        )

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ChdmanError(f"CHD não encontrado: {source}")

    result = _run(executable, ["info", "-i", str(source)], timeout)
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    if result.returncode != 0:
        raise ChdmanError(f"chdman info falhou ({result.returncode}): {output.strip()}")

    match = _SHA1_RE.search(output)
    if not match:
        raise ChdmanError(f"chdman info não retornou o SHA1 do CHD: {source}")

    size_match = _LOGICAL_SIZE_RE.search(output)
    version_match = _VERSION_RE.search(output)
    return {
        "sha1": match.group(1).lower(),
        "logical_size": int(size_match.group(1).replace(",", "")) if size_match else 0,
        "chdman_version": version_match.group(1) if version_match else None,
        "physical_size": source.stat().st_size,
        "path": str(source),
    }


def chdman_verify(path: str | Path, chdman_path: str | Path | None = None, timeout: int = 3600) -> dict[str, Any]:
    """Executa ``chdman verify -i`` e exige retorno zero."""
    executable = find_chdman(chdman_path)
    if executable is None:
        raise ChdmanError(
            "chdman.exe não foi encontrado. Configure MAME_CHDMAN, MAME_EXE_DIR "
            "ou MAME_EXECUTABLE, ou coloque chdman no PATH."
        )

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ChdmanError(f"CHD não encontrado: {source}")

    result = _run(executable, ["verify", "-i", str(source)], timeout)
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    if result.returncode != 0:
        raise ChdmanError(f"chdman verify falhou ({result.returncode}): {output.strip()}")
    return {"verified": True, "output": output, "returncode": result.returncode}


def validate_chd(path: str | Path, expected_sha1: str | None, expected_logical_size: int = 0, chdman_path: str | Path | None = None) -> tuple[bool, dict[str, Any]]:
    """Valida integridade pelo chdman e compara o SHA-1 lógico esperado."""
    verify = chdman_verify(path, chdman_path=chdman_path)
    info = chdman_info(path, chdman_path=chdman_path)
    expected = (expected_sha1 or "").strip().lower()
    logical_size = int(info.get("logical_size") or 0)
    size_ok = expected_logical_size <= 0 or logical_size == expected_logical_size
    sha1_ok = not expected or str(info["sha1"]).lower() == expected
    info.update(verify)
    info["expected_sha1"] = expected or None
    info["sha1_match"] = sha1_ok
    info["logical_size_match"] = size_ok
    return size_ok and sha1_ok, info
