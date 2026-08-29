"""Track No-Intro DAT freshness without re-downloading current files."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ...runtime.paths import data_root
from .catalog import NoIntroSystem
from .downloader import NoIntroDownload

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NoIntroLocalStatus:
    """Describe whether one local DAT matches the catalog revision."""

    system: str
    path: Path
    state: str
    local_update: str | None
    remote_update: str | None
    sha256: str | None

    @property
    def needs_update(self) -> bool:
        """Return whether an existing local DAT should be replaced."""
        return self.state in {"outdated", "unknown"}

    @property
    def missing(self) -> bool:
        """Return whether the DAT has not been downloaded yet."""
        return self.state == "missing"


class NoIntroUpdateManager:
    """Persist source revision metadata and classify local No-Intro DATs."""

    MANIFEST_NAME = "manifest.json"

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else data_root() / "sources" / "no_intro" / "dats"
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / self.MANIFEST_NAME

    def inspect(self, system: NoIntroSystem, path: Path) -> NoIntroLocalStatus:
        """Classify one local DAT using the latest catalog timestamp."""
        path = Path(path)
        entry = self._load().get(system.name.casefold())
        if not path.is_file():
            status = NoIntroLocalStatus(system.name, path, "missing", None, system.update_text, None)
        elif not entry or not entry.get("update_text"):
            status = NoIntroLocalStatus(system.name, path, "unknown", None, system.update_text, None)
        elif self._revision(entry["update_text"]) < self._revision(system.update_text):
            status = NoIntroLocalStatus(
                system.name, path, "outdated", entry.get("update_text"), system.update_text, entry.get("sha256")
            )
        else:
            status = NoIntroLocalStatus(
                system.name, path, "current", entry.get("update_text"), system.update_text, entry.get("sha256")
            )
        logger.debug(
            "[NO-INTRO][FRESHNESS] sistema=%s estado=%s local=%s remoto=%s arquivo=%s",
            system.name,
            status.state,
            status.local_update,
            status.remote_update,
            status.path,
        )
        return status

    def statuses(self, systems: tuple[NoIntroSystem, ...], destination_for) -> tuple[NoIntroLocalStatus, ...]:
        """Classify all matched systems using the supplied destination function."""
        return tuple(self.inspect(system, destination_for(system)) for system in systems)

    def update_candidates(self, systems: tuple[NoIntroSystem, ...], destination_for) -> tuple[NoIntroSystem, ...]:
        """Return only existing DATs whose recorded revision is older or unknown."""
        result = []
        for system in systems:
            status = self.inspect(system, destination_for(system))
            if status.needs_update and not status.missing:
                result.append(system)
        logger.info("[NO-INTRO][FRESHNESS] candidatos para atualização=%d", len(result))
        return tuple(result)

    def record(self, system: NoIntroSystem, download: NoIntroDownload) -> None:
        """Record the catalog revision, hash and source URL after a successful download."""
        manifest = self._load()
        manifest[system.name.casefold()] = {
            "system": system.name,
            "update_text": system.update_text,
            "sha256": download.sha256,
            "source_url": download.source_url,
            "path": str(download.path),
            "downloaded_at": datetime.now(UTC).isoformat(),
        }
        self._save(manifest)
        logger.info(
            "[NO-INTRO][FRESHNESS] registrado sistema=%s revisão=%s sha256=%s",
            system.name,
            system.update_text,
            download.sha256,
        )

    def _load(self) -> dict[str, dict[str, object]]:
        """Load the local freshness manifest, treating a missing file as empty."""
        if not self.manifest_path.is_file():
            return {}
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            logger.warning("[NO-INTRO][FRESHNESS] manifesto inválido: %s", self.manifest_path)
            return {}

    def _save(self, manifest: dict[str, dict[str, object]]) -> None:
        """Atomically persist freshness metadata."""
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.manifest_path)

    @staticmethod
    def _revision(value: str | None) -> datetime:
        """Normalize DAT-o-MATIC timestamp formats for chronological comparison."""
        if not value:
            return datetime.min.replace(tzinfo=UTC)
        value = value.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d-%H%M%S"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
        return datetime.min.replace(tzinfo=UTC)
