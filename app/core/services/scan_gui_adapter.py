"""Adapter entre a GUI do Scan ROMs e o serviço de sessão."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.services.scan_session_service import ScanSessionService


class ScanGuiAdapter:
    """Fornece à GUI uma API pequena e estável para o novo fluxo de scan."""

    def __init__(self, session_service: ScanSessionService) -> None:
        """Inicializa o adapter com a sessão configurada pelo aplicativo."""
        self.session_service = session_service

    def start(
        self,
        machines: list[dict[str, Any]],
        rom_paths: list[Path],
        *,
        xml_path: Path,
        mame_version: str,
        max_workers: int,
        manifest_directory: Path,
        progress_callback: Any = None,
        machine_callback: Any = None,
        log_callback: Any = None,
    ) -> tuple[int, Any]:
        """Inicia o novo pipeline mantendo os callbacks esperados pela GUI."""
        return self.session_service.run(
            machines,
            rom_paths,
            mame_version=mame_version,
            xml_path=xml_path,
            max_workers=max_workers,
            manifest_directory=manifest_directory,
            progress_callback=progress_callback,
            machine_callback=machine_callback,
            log_callback=log_callback,
        )

    def latest(self) -> Any | None:
        """Retorna o resultado persistido mais recente."""
        return self.session_service.latest()

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retorna o histórico resumido de scans."""
        return self.session_service.history(limit)

    def load(self, scan_id: int) -> Any | None:
        """Carrega um scan persistido."""
        return self.session_service.load(scan_id)

    def delete(self, scan_id: int) -> bool:
        """Remove um scan persistido."""
        return self.session_service.delete(scan_id)


__all__ = ["ScanGuiAdapter"]
