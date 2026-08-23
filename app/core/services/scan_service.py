"""Orquestração do Scan ROMs com persistência do resultado.

Este serviço é a ponte entre o ``RomScanEngine`` e o ``ScanRepository``.
O engine continua responsável pela descoberta/validação física; o repositório
continua responsável pela persistência SQLite.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from app.core.models.scan_result import MachineScanResult, ScanResult
from app.database.scan_repository import ScanRepository
from app.mame.rom_scan_engine import RomScanEngine


class ScanService:
    """Executa scans físicos e registra sessões completas no SQLite."""

    def __init__(
        self,
        repository: ScanRepository,
        *,
        engine_factory: Callable[..., RomScanEngine] = RomScanEngine,
    ) -> None:
        """Inicializa o serviço com repositório e fábrica do scanner.

        A fábrica é injetável para permitir testes sem filesystem real e para
        manter a camada de orquestração independente de uma implementação
        específica do engine.
        """
        self.repository = repository
        self.engine_factory = engine_factory

    def scan(
        self,
        machines: Iterable[Any],
        rom_paths: Iterable[str | Path],
        *,
        mame_version: str = "unknown",
        xml_path: str | Path | None = None,
        max_workers: int = 1,
        enable_alternate_search: bool = True,
        include_chds: bool = True,
        manifest_directory: str | Path | None = None,
        progress_callback: Callable[[int, int, Any], None] | None = None,
        machine_callback: Callable[[MachineScanResult], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> tuple[int, ScanResult]:
        """Executa um scan, agrega seus resultados e persiste a sessão.

        A persistência ocorre somente depois que o engine termina. Assim o
        banco não recebe uma sessão declarada como concluída com resultados
        parciais.
        """
        started_at = datetime.now(timezone.utc)
        engine = self.engine_factory(
            rom_paths,
            max_workers=max_workers,
            progress_callback=progress_callback,
            machine_callback=machine_callback,
            log_callback=log_callback,
            enable_alternate_search=enable_alternate_search,
            include_chds=include_chds,
            manifest_directory=manifest_directory,
        )

        machines_result = engine.scan(
            machines,
            mame_version=mame_version,
            xml_path=xml_path,
        )

        result = ScanResult(
            machines=list(machines_result),
            xml_path=Path(xml_path) if xml_path else None,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            cancelled=engine.cancelled,
        )

        scan_id = self.repository.save(result)
        return scan_id, result

    def load(self, scan_id: int) -> ScanResult | None:
        """Carrega uma sessão persistida pelo identificador."""
        return self.repository.load(scan_id)

    def latest(self) -> ScanResult | None:
        """Carrega o resultado completo da sessão mais recente."""
        scan_id = self.repository.latest_id()
        return self.repository.load(scan_id) if scan_id is not None else None

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retorna o histórico resumido das últimas sessões."""
        return self.repository.list_sessions(limit)

    def delete(self, scan_id: int) -> bool:
        """Remove uma sessão persistida e seus registros dependentes."""
        return self.repository.delete(scan_id)


__all__ = ["ScanService"]
