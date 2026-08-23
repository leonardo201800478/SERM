"""Coordenação da sessão de Scan ROMs entre GUI, engine e persistência."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from app.core.services.scan_service import ScanService


class ScanSessionService:
    """Fachada fina para a camada GUI do Scan ROMs.

    Mantém a GUI desacoplada do banco e do ``RomScanEngine``. A sessão é
    iniciada, consultada e removida exclusivamente através de ``ScanService``.
    """

    def __init__(self, scan_service: ScanService) -> None:
        """Inicializa a fachada com um serviço de scan já configurado."""
        self.scan_service = scan_service

    def run(
        self,
        machines: Iterable[Any],
        source_paths: Iterable[str | Path],
        *,
        mame_version: str,
        xml_path: str | Path | None,
        max_workers: int = 1,
        enable_alternate_search: bool = True,
        include_chds: bool = True,
        manifest_directory: str | Path | None = None,
        progress_callback: Callable[[int, int, Any], None] | None = None,
        machine_callback: Callable[[Any], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> tuple[int, Any]:
        """Executa uma sessão completa e retorna ``(scan_id, result)``."""
        return self.scan_service.scan(
            machines,
            source_paths,
            mame_version=mame_version,
            xml_path=xml_path,
            max_workers=max_workers,
            enable_alternate_search=enable_alternate_search,
            include_chds=include_chds,
            manifest_directory=manifest_directory,
            progress_callback=progress_callback,
            machine_callback=machine_callback,
            log_callback=log_callback,
        )

    def latest(self) -> Any | None:
        """Retorna a sessão persistida mais recente."""
        return self.scan_service.latest()

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retorna o histórico resumido das sessões."""
        return self.scan_service.history(limit)

    def load(self, scan_id: int) -> Any | None:
        """Carrega uma sessão específica."""
        return self.scan_service.load(scan_id)

    def delete(self, scan_id: int) -> bool:
        """Exclui uma sessão persistida."""
        return self.scan_service.delete(scan_id)


__all__ = ["ScanSessionService"]
