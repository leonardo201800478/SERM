"""Reconstrução física de CHDs por validação e cópia direta.

CHD não é reconstruído pelo projeto. O arquivo encontrado é validado usando
``chdman info`` para obter o content SHA1 e, somente quando o SHA1 corresponde
ao digest esperado pelo LISTXML, ``chdman verify`` é executado. Em caso de
qualquer divergência o arquivo é ignorado e o CHD permanece MISSING para a
reconstrução.

Destino padrão:

    <destination>/<machine>/<disk>.chd

O serviço trabalha somente com CHDs exigidos pelo ``ScanResult`` recebido;
nunca faz uma varredura genérica do HDD em busca de CHDs.
"""
from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.models.scan_result import (
    RomScanResult,
    ScanItemType,
    ScanResult,
    ScanStatus,
)
from app.mame.chdman_validator import ChdmanError, chdman_info, chdman_verify


@dataclass(frozen=True, slots=True)
class ChdReconstructionOptions:
    """Opções do processo de validação/cópia de CHDs."""

    destination: Path
    overwrite: bool = False
    chdman_path: Path | None = None
    verify_integrity: bool = True


@dataclass(frozen=True, slots=True)
class ChdCopyResult:
    """Resultado auditável de um CHD individual."""

    machine: str
    disk: str
    status: str
    action: str
    source: str | None
    destination: str | None
    expected_sha1: str
    actual_sha1: str
    verified: bool
    executable: bool
    blocking: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        """Converte o resultado para o formato usado no manifesto."""
        return {
            "machine": self.machine,
            "disk": self.disk,
            "status": self.status,
            "action": self.action,
            "source": self.source,
            "destination": self.destination,
            "expected_sha1": self.expected_sha1,
            "actual_sha1": self.actual_sha1,
            "verified": self.verified,
            "executable": self.executable,
            "blocking": self.blocking,
            "reason": self.reason,
        }


class ChdReconstructionService:
    """Valida e copia CHDs; nunca cria ou modifica o conteúdo de um CHD."""

    def __init__(self, options: ChdReconstructionOptions):
        self.options = options
        self.options.destination.mkdir(parents=True, exist_ok=True)

    def reconstruct(
        self,
        result: ScanResult,
        *,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[ChdCopyResult]:
        """Processa somente os CHDs presentes no ScanResult.

        A ordem de decisão é deliberadamente curta:

        1. CHD ausente no scan -> MISSING.
        2. Obtém content SHA1 com ``chdman info``.
        3. SHA1 divergente -> IGNORE/MISSING; não tenta reparar.
        4. SHA1 correto -> opcionalmente executa ``chdman verify``.
        5. CHD íntegro -> copia diretamente para ``<machine>/<disk>.chd``.

        O tamanho físico do arquivo não participa da identidade do CHD.
        """
        requirements = self._collect_requirements(result)
        results: list[ChdCopyResult] = []
        total = len(requirements)

        for index, item in enumerate(requirements, start=1):
            copy_result = self._process(item)
            results.append(copy_result)
            if progress_callback:
                progress_callback(index, total, f"{item.machine_name}:{item.rom_name}")

        return results

    @staticmethod
    def _collect_requirements(result: ScanResult) -> list[RomScanResult]:
        """Extrai CHDs únicos do scan, preservando a ordem das máquinas."""
        requirements: list[RomScanResult] = []
        seen: set[tuple[str, str, str]] = set()
        for machine in result.machines:
            for item in machine.roms:
                if item.item_type is not ScanItemType.DISK:
                    continue
                key = (
                    item.machine_name,
                    item.rom_name.lower(),
                    (item.expected_sha1 or "").lower(),
                )
                if key in seen:
                    continue
                seen.add(key)
                requirements.append(item)
        return requirements

    def _process(self, item: RomScanResult) -> ChdCopyResult:
        """Valida e copia um único CHD, sem alterar o original."""
        expected = (item.expected_sha1 or "").strip().lower()
        source = self._source_path(item)
        destination = self.options.destination / item.machine_name / f"{item.rom_name}.chd"

        if source is None or not source.is_file():
            return ChdCopyResult(
                machine=item.machine_name,
                disk=item.rom_name,
                status=ScanStatus.MISSING.value,
                action="missing",
                source=str(source) if source else None,
                destination=str(destination),
                expected_sha1=expected,
                actual_sha1="",
                verified=False,
                executable=False,
                blocking=not item.optional,
                reason="CHD obrigatório não foi encontrado na origem física do scan.",
            )

        try:
            info = chdman_info(source, chdman_path=self.options.chdman_path)
            actual = str(info.get("sha1") or "").lower()
        except ChdmanError as exc:
            return ChdCopyResult(
                machine=item.machine_name,
                disk=item.rom_name,
                status=ScanStatus.MISSING.value,
                action="ignore",
                source=str(source),
                destination=str(destination),
                expected_sha1=expected,
                actual_sha1="",
                verified=False,
                executable=False,
                blocking=not item.optional,
                reason=f"CHD ignorado: não foi possível obter o content SHA1 com chdman: {exc}",
            )

        if expected and actual != expected:
            return ChdCopyResult(
                machine=item.machine_name,
                disk=item.rom_name,
                status=ScanStatus.MISSING.value,
                action="ignore",
                source=str(source),
                destination=str(destination),
                expected_sha1=expected,
                actual_sha1=actual,
                verified=False,
                executable=False,
                blocking=not item.optional,
                reason=(
                    "CHD ignorado: content SHA1 inválido. "
                    f"Esperado {expected}; encontrado {actual}. "
                    "O arquivo permanece como MISSING e não será reconstruído."
                ),
            )

        verified = False
        if self.options.verify_integrity:
            try:
                chdman_verify(source, chdman_path=self.options.chdman_path)
                verified = True
            except ChdmanError as exc:
                return ChdCopyResult(
                    machine=item.machine_name,
                    disk=item.rom_name,
                    status=ScanStatus.MISSING.value,
                    action="ignore",
                    source=str(source),
                    destination=str(destination),
                    expected_sha1=expected,
                    actual_sha1=actual,
                    verified=False,
                    executable=False,
                    blocking=not item.optional,
                    reason=f"CHD ignorado: chdman verify falhou: {exc}",
                )

        try:
            self._copy(source, destination)
        except OSError as exc:
            return ChdCopyResult(
                machine=item.machine_name,
                disk=item.rom_name,
                status=ScanStatus.ERROR.value,
                action="error",
                source=str(source),
                destination=str(destination),
                expected_sha1=expected,
                actual_sha1=actual,
                verified=verified,
                executable=False,
                blocking=True,
                reason=f"CHD validado, mas não foi possível copiá-lo: {exc}",
            )

        return ChdCopyResult(
            machine=item.machine_name,
            disk=item.rom_name,
            status=ScanStatus.VALID.value,
            action="copy",
            source=str(source),
            destination=str(destination),
            expected_sha1=expected,
            actual_sha1=actual,
            verified=verified,
            executable=True,
            blocking=False,
            reason="CHD validado pelo content SHA1 e chdman verify; copiado sem alteração.",
        )

    @staticmethod
    def _source_path(item: RomScanResult) -> Path | None:
        """Obtém somente a origem física conhecida pelo scanner."""
        if item.path is not None and item.path.is_file():
            return item.path
        if item.location is not None and item.location.is_file():
            return item.location
        return item.path

    def _copy(self, source: Path, destination: Path) -> None:
        """Copia o CHD preservando bytes; nunca usa chdman para gerar outro CHD."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and not self.options.overwrite:
            return
        partial = destination.with_name(destination.name + ".partial")
        try:
            shutil.copy2(source, partial)
            os.replace(partial, destination)
        finally:
            partial.unlink(missing_ok=True)
