"""Local scan and reconstruction input for ares firmware metadata."""

from __future__ import annotations

import hashlib
import json
import urllib.request
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
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
    sha256: str = ""
    size: int | None = None
    sha1: str = ""
    md5: str = ""
    crc32: str = ""
    validation: tuple[str, ...] = ()
    output_path: str = ""
    aliases: tuple[str, ...] = ()
    profile_id: str = ""

    @property
    def is_verifiable(self) -> bool:
        return bool(self.sha256 or self.sha1 or self.md5 or self.crc32)

    @property
    def key(self) -> str:
        return "|".join(
            (
                self.profile_id.casefold(),
                self.name.casefold(),
                self.output_path.casefold(),
                self.sha256,
                self.sha1,
                self.md5,
                self.crc32,
            )
        )


@dataclass(frozen=True, slots=True)
class AresFirmwareMatch:
    entry: AresFirmwareEntry
    path: str
    archive_member: str | None = None

    def to_evidence(self) -> dict[str, object]:
        evidence: dict[str, object] = {
            "kind": "firmware",
            "output_name": self.entry.output_path or self.entry.name,
            "system": self.entry.system,
            "description": self.entry.description,
            "required": self.entry.required,
            "status": "CURRENT",
            "categories": ["type:bios"],
        }
        for name in ("sha256", "sha1", "md5", "crc32"):
            value = getattr(self.entry, name)
            if value:
                evidence[f"expected_{name}"] = value
        if self.entry.size is not None:
            evidence["expected_size"] = self.entry.size
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
    emulator: str = "ares"


@dataclass(frozen=True, slots=True)
class AresUnassignedFirmware:
    emulator: str
    firmware_type: str
    region: str
    location: str


class AresFirmwareService:
    """Load RetroBIOS profiles and audit user-owned files by catalog checksums."""

    CATALOG_URL = "https://abdess.github.io/retrobios/api/v1/emulators.json"
    CATALOG_CACHE = data_root() / "catalog" / "retrobios_emulators.json"
    MAX_CATALOG_BYTES = 8 * 1024 * 1024
    CHUNK_SIZE = 1024 * 1024
    PROFILE_ALIASES = {
        "super_zsnes": ("superzsnes",),
        "rmg": ("mupen64plus_next", "mupen64plus_next_develop"),
        "ryujinx_nextendo": ("ryujinx",),
        "xenia_canary": ("xenia",),
        "dosbox_staging": ("dosbox-staging",),
        "dosbox_x": ("dosbox-x",),
    }

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
    def load_catalog(
        cls, *, emulator: str = "ares", refresh: bool = False
    ) -> tuple[str, tuple[AresFirmwareEntry, ...]]:
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
                return cls.load_catalog(emulator=emulator, refresh=True)

        if payload is None:
            raise AresFirmwareError("O catálogo RetroBIOS não retornou dados.")
        entries, version = cls._parse_catalog(payload, emulator=emulator)
        if not entries:
            raise AresFirmwareError(
                f"O RetroBIOS não possui perfil com arquivos para '{emulator}'."
            )
        return version, entries

    @classmethod
    def scan(
        cls,
        source: str | Path,
        entries: tuple[AresFirmwareEntry, ...],
        *,
        catalog_version: str = "unknown",
        emulator: str = "ares",
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
    ) -> AresFirmwareScan:
        root = Path(source).expanduser().resolve()
        if not root.is_dir():
            raise AresFirmwareError(f"Diretório de origem do {emulator} não encontrado: {root}")
        if emulator.casefold() == "mame":
            raise AresFirmwareError("O scan RetroBIOS não opera no MAME.")
        hash_index = cls._build_hash_index(entries)
        name_index = cls._build_name_index(entries)

        candidates = sorted(
            (path for path in root.rglob("*") if path.is_file()),
            key=lambda path: str(path).casefold(),
        )
        found: dict[str, AresFirmwareMatch] = {}
        examined = 0
        total = len(candidates)
        for candidate in candidates:
            if cancel_callback and cancel_callback():
                raise AresFirmwareError(f"Scan de firmware do {emulator} cancelado.")
            try:
                if candidate.suffix.casefold() == ".zip":
                    cls._scan_zip(candidate, hash_index, name_index, found)
                else:
                    identity = cls._hash_file(candidate)
                    cls._record_matches(hash_index, name_index, identity, candidate, None, found)
            except (OSError, zipfile.BadZipFile, RuntimeError):
                pass
            examined += 1
            if progress_callback:
                progress_callback(examined, total)

        matches = tuple(found[key] for key in sorted(found))
        matched_names = set(found)
        missing = tuple(entry for entry in entries if entry.key not in matched_names)
        return AresFirmwareScan(catalog_version, str(root), matches, missing, examined, emulator)

    @classmethod
    def write_filter_file(
        cls, scan: AresFirmwareScan, selected: tuple[AresFirmwareMatch, ...]
    ) -> Path:
        """Write SERM's reconstruction input for the selected, hash-verified files."""
        run_id = uuid4().hex
        emulator = scan.emulator.casefold()
        is_ares = emulator == "ares"
        output = scans_root() / "filtered" / f"{emulator}_firmware" / f"{run_id}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": "SERM-FILTER-V2",
            "filter_run_id": run_id,
            "scan_id": run_id,
            "source": "ares-firmware" if is_ares else emulator,
            "system": emulator,
            "catalog_label": f"RetroBIOS {emulator} {scan.catalog_version}",
            "scan_type": "firmware",
            "created_at": datetime.now(UTC).isoformat(),
            "source_directory": scan.source_directory,
            "filters": (
                {"verification": "catalog", "preserve_destination_files": True}
                if is_ares
                else {"bios_only": True, "preserve_destination_files": True}
            ),
            "evidence": [match.to_evidence() for match in selected],
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return output

    @classmethod
    def clean_invalid_files(
        cls, directory: str | Path, entries: tuple[AresFirmwareEntry, ...]
    ) -> tuple[Path, ...]:
        """Remove catalog-named files whose bytes fail every available identity."""
        root = Path(directory).expanduser().resolve()
        if not root.is_dir():
            return ()
        entries_by_name: dict[str, list[AresFirmwareEntry]] = {}
        for entry in entries:
            if entry.is_verifiable:
                names = {Path(entry.name).name.casefold(), Path(entry.output_path).name.casefold()}
                for alias in entry.aliases:
                    names.add(Path(alias).name.casefold())
                for name in names:
                    if name:
                        entries_by_name.setdefault(name, []).append(entry)
        removed: list[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            candidates = entries_by_name.get(path.name.casefold())
            if not candidates:
                continue
            try:
                identity = cls._hash_file(path)
                if not any(cls._matches_entry(identity, entry) for entry in candidates):
                    path.unlink()
                    removed.append(path)
            except OSError:
                continue
        return tuple(removed)

    @classmethod
    def _scan_zip(
        cls,
        path: Path,
        hash_index: dict[tuple[str, str], tuple[AresFirmwareEntry, ...]],
        name_index: dict[str, tuple[AresFirmwareEntry, ...]],
        found: dict[str, AresFirmwareMatch],
    ) -> None:
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                with archive.open(member, "r") as stream:
                    identity = cls._hash_stream(stream)
                cls._record_matches(hash_index, name_index, identity, path, member.filename, found)

    @staticmethod
    def _build_hash_index(
        entries: tuple[AresFirmwareEntry, ...],
    ) -> dict[tuple[str, str], tuple[AresFirmwareEntry, ...]]:
        index: dict[tuple[str, str], list[AresFirmwareEntry]] = {}
        for entry in entries:
            for algorithm in ("sha256", "sha1", "md5", "crc32"):
                digest = getattr(entry, algorithm)
                if digest:
                    index.setdefault((algorithm, digest.casefold()), []).append(entry)
        return {key: tuple(value) for key, value in index.items()}

    @staticmethod
    def _build_name_index(
        entries: tuple[AresFirmwareEntry, ...],
    ) -> dict[str, tuple[AresFirmwareEntry, ...]]:
        """Indexa apenas entradas sem hash para fallback pelo nome do arquivo."""
        index: dict[str, list[AresFirmwareEntry]] = {}
        for entry in entries:
            if entry.is_verifiable:
                continue
            names = {
                Path(entry.name).name.casefold(),
                Path(entry.output_path).name.casefold(),
                *(Path(alias).name.casefold() for alias in entry.aliases),
            }
            for name in names:
                if name:
                    index.setdefault(name, []).append(entry)
        return {key: tuple(value) for key, value in index.items()}

    @classmethod
    def _record_matches(
        cls,
        hash_index: dict[tuple[str, str], tuple[AresFirmwareEntry, ...]],
        name_index: dict[str, tuple[AresFirmwareEntry, ...]],
        identity: dict[str, object],
        path: Path,
        member: str | None,
        found: dict[str, AresFirmwareMatch],
    ) -> None:
        candidates: dict[str, AresFirmwareEntry] = {}
        for algorithm in ("sha256", "sha1", "md5", "crc32"):
            digest = str(identity.get(algorithm) or "").casefold()
            for entry in hash_index.get((algorithm, digest), ()):
                candidates[entry.key] = entry
        for entry in candidates.values():
            if entry.key not in found and cls._matches_entry(identity, entry):
                found[entry.key] = AresFirmwareMatch(entry, str(path), member)

        # Entradas sem hash só podem ser associadas pelo nome do arquivo.
        # Entradas que possuem hash continuam exigindo validação criptográfica.
        member_name = Path(member).name.casefold() if member else path.name.casefold()
        for entry in name_index.get(member_name, ()):
            if entry.key not in found:
                found[entry.key] = AresFirmwareMatch(entry, str(path), member)

    @staticmethod
    def _matches_entry(identity: dict[str, object], entry: AresFirmwareEntry) -> bool:
        if not entry.is_verifiable:
            return False
        if entry.size is not None and identity.get("size") != entry.size:
            return False
        return all(
            not expected or str(identity.get(name, "")).casefold() == expected.casefold()
            for name, expected in (
                ("sha256", entry.sha256),
                ("sha1", entry.sha1),
                ("md5", entry.md5),
                ("crc32", entry.crc32),
            )
        )

    @classmethod
    def _parse_catalog(
        cls, payload: object, *, emulator: str = "ares"
    ) -> tuple[tuple[AresFirmwareEntry, ...], str]:
        profiles: list[tuple[str, dict]] = []
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            for item in payload["items"]:
                if not isinstance(item, dict) or not isinstance(item.get("profile"), dict):
                    continue
                profiles.append((str(item.get("id") or ""), item["profile"]))
        elif isinstance(payload, dict) and isinstance(payload.get("files"), list):
            profiles.append((str(payload.get("emulator") or emulator), payload))

        target = emulator.casefold()
        if target == "mame":
            return (), "excluded"
        if target == "retroarch":
            selected = [
                (profile_id, profile)
                for profile_id, profile in profiles
                if not profile_id.casefold().startswith("mame")
                and not str(profile.get("emulator") or "").casefold().startswith("mame")
                and "libretro" in str(profile.get("type") or "").casefold()
            ]
        else:
            aliases = {target, *(alias.casefold() for alias in cls.PROFILE_ALIASES.get(target, ()))}
            selected = [
                (profile_id, profile)
                for profile_id, profile in profiles
                if profile_id.casefold() in aliases
                or str(profile.get("emulator") or "").casefold() in aliases
            ]

        entries: dict[str, AresFirmwareEntry] = {}
        versions: list[str] = []
        for profile_id, profile in selected:
            version = str(
                profile.get("core_version")
                or profile.get("version")
                or profile.get("profiled_date")
                or "unknown"
            )
            versions.append(version)
            rom_path = str(profile.get("rom_path") or "").strip()
            for item in profile.get("files", []):
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or item.get("filename") or item.get("file") or "").strip()
                if not name:
                    continue
                output_path = cls._output_path(
                    str(item.get("path") or "").strip(), name, rom_path
                )
                if output_path is None:
                    continue
                digest_values: dict[str, str] = {}
                for algorithm, length in (("sha256", 64), ("sha1", 40), ("md5", 32), ("crc32", 8)):
                    digest = str(item.get(algorithm) or "").strip().casefold()
                    if digest and len(digest) == length:
                        try:
                            int(digest, 16)
                        except ValueError:
                            continue
                        digest_values[algorithm] = digest
                size_value = item.get("size")
                try:
                    size = int(size_value) if size_value is not None else None
                except (TypeError, ValueError):
                    size = None
                validation = item.get("validation")
                validation_items = (
                    tuple(str(value).casefold() for value in validation)
                    if isinstance(validation, list)
                    else ()
                )
                aliases_value = item.get("aliases")
                file_aliases = (
                    tuple(str(value) for value in aliases_value if str(value).strip())
                    if isinstance(aliases_value, list)
                    else ()
                )
                entry = AresFirmwareEntry(
                    name=name,
                    system=str(item.get("system") or profile.get("display_name") or profile_id),
                    description=str(item.get("description") or item.get("notes") or ""),
                    required=bool(item.get("required", True)),
                    sha256=digest_values.get("sha256", ""),
                    size=size,
                    sha1=digest_values.get("sha1", ""),
                    md5=digest_values.get("md5", ""),
                    crc32=digest_values.get("crc32", ""),
                    validation=validation_items,
                    output_path=output_path,
                    aliases=file_aliases,
                    profile_id=profile_id,
                )
                entries.setdefault(entry.key, entry)
        catalog_version = payload.get("generated_at") if isinstance(payload, dict) else None
        version = str(catalog_version or (versions[0] if versions else "unknown"))
        return tuple(entries.values()), version

    @staticmethod
    def _output_path(file_path: str, name: str, rom_path: str) -> str | None:
        output = file_path or name
        if file_path and not PurePosixPath(output.replace("\\", "/")).suffix:
            output = f"{output.rstrip('/\\')}/{PurePosixPath(name.replace('\\', '/')).name}"
        elif not file_path and rom_path:
            output = f"{rom_path.rstrip('/\\')}/{name}"
        normalized = PurePosixPath(output.replace("\\", "/"))
        if (
            normalized.is_absolute()
            or PureWindowsPath(output).drive
            or ".." in normalized.parts
            or not normalized.parts
        ):
            return None
        return normalized.as_posix()

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
            return str(cls._hash_stream(stream)["sha256"])

    @classmethod
    def _sha256_stream(cls, stream) -> str:
        return str(cls._hash_stream(stream)["sha256"])

    @classmethod
    def _hash_file(cls, path: Path) -> dict[str, object]:
        with path.open("rb") as stream:
            return cls._hash_stream(stream)

    @classmethod
    def _hash_stream(cls, stream) -> dict[str, object]:
        sha256 = hashlib.sha256()
        sha1 = hashlib.sha1(usedforsecurity=False)
        md5 = hashlib.md5(usedforsecurity=False)
        crc32 = 0
        size = 0
        while chunk := stream.read(cls.CHUNK_SIZE):
            size += len(chunk)
            sha256.update(chunk)
            sha1.update(chunk)
            md5.update(chunk)
            crc32 = zlib.crc32(chunk, crc32)
        return {
            "size": size,
            "sha256": sha256.hexdigest(),
            "sha1": sha1.hexdigest(),
            "md5": md5.hexdigest(),
            "crc32": f"{crc32 & 0xFFFFFFFF:08x}",
        }


__all__ = [
    "AresFirmwareEntry",
    "AresFirmwareError",
    "AresFirmwareMatch",
    "AresFirmwareScan",
    "AresFirmwareService",
    "AresUnassignedFirmware",
]
