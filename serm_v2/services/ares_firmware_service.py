"""Local scan and reconstruction input for ares firmware metadata."""

from __future__ import annotations

import hashlib
import json
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

from ..runtime.paths import data_root, scans_root


class AresFirmwareError(RuntimeError):
    """Actionable ares firmware scan or catalog error."""


@dataclass(frozen=True, slots=True)
class AresFirmwareEntry:
    name: str
    system: str
    description: str
    required: bool
    sha256: str
    size: int | None = None


@dataclass(frozen=True, slots=True)
class AresFirmwareMatch:
    entry: AresFirmwareEntry
    path: str
    archive_member: str | None = None

    def to_evidence(self) -> dict[str, object]:
        evidence: dict[str, object] = {
            "kind": "ares_firmware",
            "output_name": self.entry.name,
            "system": self.entry.system,
            "description": self.entry.description,
            "required": self.entry.required,
            "sha256": self.entry.sha256,
        }
        if self.archive_member:
            evidence["archive_path"] = self.path
            evidence["archive_member"] = self.archive_member
        else:
            evidence["path"] = self.path
        return evidence


@dataclass(frozen=True, slots=True)
class AresFirmwareScan:
    catalog_version: str
    source_directory: str
    matches: tuple[AresFirmwareMatch, ...]
    missing: tuple[AresFirmwareEntry, ...]
    files_examined: int


@dataclass(frozen=True, slots=True)
class AresUnassignedFirmware:
    emulator: str
    firmware_type: str
    region: str
    location: str


class AresFirmwareService:
    """Fetch the ares profile and match user-owned files by SHA-256."""

    CATALOG_URL = "https://abdess.github.io/retrobios/api/v1/emulators.json"
    CATALOG_CACHE = data_root() / "catalog" / "retrobios_emulators.json"
    MAX_CATALOG_BYTES = 8 * 1024 * 1024
    CHUNK_SIZE = 1024 * 1024

    @classmethod
    def read_unassigned_firmware(
        cls, settings_path: str | Path
    ) -> tuple[AresUnassignedFirmware, ...]:
        """Read ares firmware assignments and return unset or unavailable paths.

        ares stores each assignment under ``<Emulator>/Firmware/<Type>.<Region>``.
        Its firmware panel considers a location valid when the referenced file exists.
        """
        path = Path(settings_path).expanduser()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise AresFirmwareError(f"Não foi possível ler o settings.bml do ares: {exc}") from exc

        parents: list[tuple[int, str]] = []
        missing: list[AresUnassignedFirmware] = []
        assignments_found = 0
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", ";")):
                continue
            indent = len(line) - len(line.lstrip())
            while parents and parents[-1][0] >= indent:
                parents.pop()
            if ":" not in stripped:
                parents.append((indent, stripped))
                continue

            name, raw_location = stripped.split(":", 1)
            ancestors = [part for _level, part in parents]
            try:
                firmware_index = next(
                    index for index, part in enumerate(ancestors)
                    if part.casefold() == "firmware"
                )
            except StopIteration:
                continue
            if firmware_index == 0:
                continue
            identity = name.strip().rsplit(".", 1)
            if len(identity) != 2:
                continue
            assignments_found += 1
            emulator = ancestors[firmware_index - 1]
            firmware_type, region = identity
            location = raw_location.strip().strip('"')
            target = Path(location).expanduser() if location else None
            if target is None or not target.is_file():
                missing.append(
                    AresUnassignedFirmware(emulator, firmware_type, region, location)
                )
        if not assignments_found:
            raise AresFirmwareError(
                "O settings.bml não contém atribuições de firmware do ares; "
                "abra e salve a tela Firmware do ares antes de exportar."
            )
        return tuple(missing)

    @classmethod
    def load_catalog(cls, *, refresh: bool = False) -> tuple[str, tuple[AresFirmwareEntry, ...]]:
        payload: object | None = None
        if refresh:
            try:
                request = urllib.request.Request(
                    cls.CATALOG_URL,
                    headers={"User-Agent": "SERM/2.x", "Accept": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    raw = response.read(cls.MAX_CATALOG_BYTES + 1)
                if len(raw) > cls.MAX_CATALOG_BYTES:
                    raise AresFirmwareError("O catálogo RetroBIOS ultrapassou o limite de 8 MiB.")
                payload = json.loads(raw.decode("utf-8"))
                cls.CATALOG_CACHE.parent.mkdir(parents=True, exist_ok=True)
                cls.CATALOG_CACHE.write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
            except AresFirmwareError:
                raise
            except Exception as exc:  # noqa: BLE001
                if cls.CATALOG_CACHE.is_file():
                    payload = cls._read_cache()
                else:
                    raise AresFirmwareError(
                        f"Não foi possível atualizar o catálogo RetroBIOS: {exc}"
                    ) from exc
        else:
            payload = cls._read_cache()
            if payload is None:
                return cls.load_catalog(refresh=True)

        if payload is None:
            raise AresFirmwareError("O catálogo RetroBIOS não retornou dados.")
        entries, version = cls._parse_catalog(payload)
        if not entries:
            raise AresFirmwareError(
                "O catálogo foi lido, mas não encontrei o perfil do ares ou seus hashes SHA-256."
            )
        return version, entries

    @classmethod
    def scan(
        cls,
        source: str | Path,
        entries: tuple[AresFirmwareEntry, ...],
        *,
        catalog_version: str = "unknown",
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
    ) -> AresFirmwareScan:
        root = Path(source).expanduser().resolve()
        if not root.is_dir():
            raise AresFirmwareError(f"Pasta de firmware do ares não encontrada: {root}")

        by_hash: dict[str, list[AresFirmwareEntry]] = {}
        for entry in entries:
            if entry.sha256:
                by_hash.setdefault(entry.sha256.casefold(), []).append(entry)

        candidates = sorted(
            (path for path in root.rglob("*") if path.is_file()),
            key=lambda path: str(path).casefold(),
        )
        found: dict[str, AresFirmwareMatch] = {}
        examined = 0
        total = len(candidates)
        for candidate in candidates:
            if cancel_callback and cancel_callback():
                raise AresFirmwareError("Scan de firmware cancelado.")
            try:
                if candidate.suffix.casefold() == ".zip":
                    cls._scan_zip(candidate, by_hash, found)
                else:
                    digest = cls._sha256_file(candidate)
                    for entry in by_hash.get(digest, ()):
                        found.setdefault(
                            entry.name.casefold(), AresFirmwareMatch(entry, str(candidate))
                        )
            except (OSError, zipfile.BadZipFile, RuntimeError):
                pass
            examined += 1
            if progress_callback:
                progress_callback(examined, total)

        matches = tuple(
            found[key]
            for key in sorted(found)
        )
        matched_names = set(found)
        missing = tuple(entry for entry in entries if entry.name.casefold() not in matched_names)
        return AresFirmwareScan(catalog_version, str(root), matches, missing, examined)

    @classmethod
    def write_filter_file(
        cls, scan: AresFirmwareScan, selected: tuple[AresFirmwareMatch, ...]
    ) -> Path:
        """Write SERM's reconstruction input for the selected, hash-verified files."""
        run_id = uuid4().hex
        output = scans_root() / "filtered" / "ares_firmware" / f"{run_id}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": "SERM-FILTER-V1",
            "filter_run_id": run_id,
            "scan_id": run_id,
            "source": "ares-firmware",
            "system": "ares",
            "catalog_label": f"RetroBIOS ares {scan.catalog_version}",
            "scan_type": "firmware",
            "created_at": datetime.now(UTC).isoformat(),
            "source_directory": scan.source_directory,
            "filters": {"verification": "sha256"},
            "evidence": [match.to_evidence() for match in selected],
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return output

    @classmethod
    def clean_invalid_files(
        cls, directory: str | Path, entries: tuple[AresFirmwareEntry, ...]
    ) -> tuple[Path, ...]:
        """Remove only catalog-named local files whose bytes fail every listed hash."""
        root = Path(directory).expanduser().resolve()
        if not root.is_dir():
            return ()
        allowed_hashes: dict[str, set[str]] = {}
        for entry in entries:
            if entry.sha256:
                allowed_hashes.setdefault(entry.name.casefold(), set()).add(entry.sha256.casefold())
        removed: list[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            known_hashes = allowed_hashes.get(path.name.casefold())
            if not known_hashes:
                continue
            try:
                if cls._sha256_file(path).casefold() not in known_hashes:
                    path.unlink()
                    removed.append(path)
            except OSError:
                continue
        return tuple(removed)

    @classmethod
    def _scan_zip(
        cls,
        path: Path,
        by_hash: dict[str, list[AresFirmwareEntry]],
        found: dict[str, AresFirmwareMatch],
    ) -> None:
        expected_names = {
            entry.name.casefold() for candidates in by_hash.values() for entry in candidates
        }
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir() or Path(member.filename).name.casefold() not in expected_names:
                    continue
                with archive.open(member, "r") as stream:
                    digest = cls._sha256_stream(stream)
                for entry in by_hash.get(digest, ()):
                    found.setdefault(
                        entry.name.casefold(),
                        AresFirmwareMatch(entry, str(path), member.filename),
                    )

    @classmethod
    def _parse_catalog(cls, payload: object) -> tuple[tuple[AresFirmwareEntry, ...], str]:
        candidates: list[dict] = []

        def visit(value: object, parent_key: str = "") -> None:
            if isinstance(value, dict):
                identity = " ".join(
                    str(value.get(key, ""))
                    for key in ("emulator", "slug", "id", "name", "key")
                ).casefold()
                has_files = isinstance(value.get("files"), list)
                if has_files and ("ares" in identity.split() or parent_key.casefold() == "ares"):
                    candidates.append(value)
                for key, child in value.items():
                    visit(child, str(key))
            elif isinstance(value, list):
                for child in value:
                    visit(child, parent_key)

        visit(payload)
        profile = max(candidates, key=lambda row: len(row.get("files", [])), default=None)
        if profile is None:
            return (), "unknown"

        entries: dict[tuple[str, str], AresFirmwareEntry] = {}
        raw_files = profile.get("files", [])
        for item in raw_files:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("filename") or item.get("file") or "").strip()
            digest = str(item.get("sha256") or "").strip().casefold()
            if not name:
                continue
            if digest:
                if len(digest) != 64:
                    continue
                try:
                    int(digest, 16)
                except ValueError:
                    continue
            size_value = item.get("size")
            try:
                size = int(size_value) if size_value is not None else None
            except (TypeError, ValueError):
                size = None
            entry = AresFirmwareEntry(
                name=name,
                system=str(item.get("system") or "ares"),
                description=str(item.get("description") or item.get("notes") or ""),
                required=bool(item.get("required", True)),
                sha256=digest,
                size=size,
            )
            entries[(name.casefold(), digest)] = entry
        version = str(
            profile.get("core_version")
            or profile.get("version")
            or profile.get("profiled_date")
            or "unknown"
        )
        return tuple(entries.values()), version

    @classmethod
    def _read_cache(cls) -> object | None:
        try:
            if cls.CATALOG_CACHE.stat().st_size > cls.MAX_CATALOG_BYTES:
                return None
            return json.loads(cls.CATALOG_CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None

    @classmethod
    def _sha256_file(cls, path: Path) -> str:
        with path.open("rb") as stream:
            return cls._sha256_stream(stream)

    @classmethod
    def _sha256_stream(cls, stream) -> str:
        digest = hashlib.sha256()
        while chunk := stream.read(cls.CHUNK_SIZE):
            digest.update(chunk)
        return digest.hexdigest()


__all__ = [
    "AresFirmwareEntry",
    "AresFirmwareError",
    "AresFirmwareMatch",
    "AresFirmwareScan",
    "AresFirmwareService",
    "AresUnassignedFirmware",
]
