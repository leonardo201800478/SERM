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
    repository_path: str = ""
    release_asset: str = ""
    catalog_available: bool = False
    gap_layer: str = ""
    gap_status: str = ""
    gap_in_repo: bool | None = None
    gap_reason: str = ""
    container_name: str = ""
    archive_required: bool = False
    region: str = ""

    @property
    def coverage_label(self) -> str:
        if self.gap_layer == "emulator":
            if self.gap_status == "bios":
                return "LACUNA DE COBERTURA" if self.gap_in_repo else "LACUNA DE COBERTURA (NÃO LOCALIZADO)"
            if self.gap_status:
                return f"COBERTURA: {self.gap_status.upper()}"
        return "SEM LACUNA REGISTRADA"

    @property
    def distribution_label(self) -> str:
        """Classifica a origem prática do arquivo para a próxima etapa do SERM."""
        if self.catalog_available:
            if self.release_asset:
                return "OBTENÇÃO: RELEASE"
            if self.repository_path:
                return "OBTENÇÃO: REPOSITÓRIO"
            return "OBTENÇÃO: CATALOGADA"
        if self.gap_layer == "emulator" and self.gap_status == "bios":
            return "OBTENÇÃO: LACUNA"
        return "OBTENÇÃO: NÃO DISPONÍVEL"

    def panel_state(self, present: bool, *, match_mode: str = "hash") -> str:
        """Classifica o estado visual do item considerando a presença local."""
        if not self.required:
            return "HLE / OPCIONAL"
        if present:
            if match_mode == "invalid":
                return "CONFIGURADO — HASH INVÁLIDO"
            if match_mode == "configured":
                return "CONFIGURADO — SEM HASH"
            if match_mode == "archive":
                return "PRESENTE — ARQUIVO COMPATÍVEL"
            if self.is_verifiable and match_mode == "name":
                return "PRESENTE — NOME COMPATÍVEL"
            return "VALIDADO" if self.is_verifiable else "PRESENTE — HASH NÃO VERIFICÁVEL"
        if self.catalog_available:
            return "AUSENTE — DISPONÍVEL"
        return "AUSENTE — NÃO DISPONÍVEL"

    def panel_state_detail(self, present: bool, *, match_mode: str = "hash") -> str:
        if not self.required:
            return "Arquivo opcional; o emulador possui fallback/HLE."
        if present:
            if match_mode == "invalid":
                return "O ARES está configurado para este arquivo, mas o SHA-256 não corresponde ao firmware declarado no código-fonte."
            if match_mode == "configured":
                return "O ARES está configurado para este arquivo; o código-fonte não fornece SHA-256 para esta entrada."
            if match_mode == "archive":
                return f"Arquivo encontrado dentro de {self.container_name}; o contêiner é aceito pelo emulador."
            if self.is_verifiable and match_mode == "name":
                return "Arquivo encontrado pelo nome; o hash do catálogo não coincidiu."
            if self.is_verifiable:
                return "Arquivo encontrado; hash correto."
            return "Arquivo encontrado; catálogo não fornece hash. Identificação por nome."
        if self.catalog_available:
            return "Arquivo não encontrado localmente; RetroBIOS possui o arquivo."
        return "Arquivo exigido pelo emulador; RetroBIOS não possui payload."

    @property
    def availability_label(self) -> str:
        if self.catalog_available:
            if self.release_asset:
                return "DISPONÍVEL (RELEASE)"
            if self.repository_path:
                return "DISPONÍVEL (REPOSITÓRIO)"
            return "CATALOGADO"
        return "NÃO LOCALIZADO NO ACERVO"

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
                self.region.casefold(),
            )
        )


@dataclass(frozen=True, slots=True)
class AresFirmwareMatch:
    entry: AresFirmwareEntry
    path: str
    archive_member: str | None = None
    match_mode: str = "hash"

    def to_evidence(self) -> dict[str, object]:
        evidence: dict[str, object] = {
            "match_mode": self.match_mode,
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
        if self.archive_member and self.entry.container_name:
            evidence["container_output_name"] = self.entry.container_name
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
    invalid: tuple[AresFirmwareMatch, ...] = ()
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
    DATABASE_URL = "https://abdess.github.io/retrobios/api/v1/database.json"
    GAPS_URL = "https://abdess.github.io/retrobios/api/v1/gaps.json"
    CATALOG_CACHE = data_root() / "catalog" / "retrobios_emulators.json"
    DATABASE_CACHE = data_root() / "catalog" / "retrobios_database.json"
    GAPS_CACHE = data_root() / "catalog" / "retrobios_gaps.json"
    MAX_CATALOG_BYTES = 8 * 1024 * 1024
    MAX_DATABASE_BYTES = 32 * 1024 * 1024
    MAX_GAPS_BYTES = 8 * 1024 * 1024
    CHUNK_SIZE = 1024 * 1024
    # Definições de firmware extraídas diretamente do código-fonte do ARES.
    # Elas têm precedência sobre o RetroBIOS para identificar o firmware que o
    # emulador realmente declara/carrega. O revision fixa a referência auditada.
    ARES_SOURCE_REVISION = "4cb8d92b441557cb6bcaf133c4cbc7f6819b1122"
    ARES_SOURCE_FIRMWARE = (
        {"system": "MSX2", "name": "MAIN", "region": "Japan", "sha256": "0c672d86ead61a97f49a583b88b7c1905da120645cd44f0c9f2baf4f4631e0b1", "source_path": "desktop-ui/emulator/msx2.cpp"},
        {"system": "MSX2", "name": "SUB", "region": "Japan", "sha256": "6c6f421a10c428d960b7ecc990f99af1c638147f747bddca7b0bf0e2ab738300", "source_path": "desktop-ui/emulator/msx2.cpp"},
        {"system": "Saturn", "name": "BIOS", "region": "US", "source_path": "desktop-ui/emulator/saturn.cpp"},
        {"system": "Saturn", "name": "BIOS", "region": "Japan", "source_path": "desktop-ui/emulator/saturn.cpp"},
        {"system": "Saturn", "name": "BIOS", "region": "Europe", "source_path": "desktop-ui/emulator/saturn.cpp"},
        {"system": "Mega CD", "name": "BIOS", "region": "US", "sha256": "fb477cdbf94c84424c2feca4fe40656d85393fe7b7b401911b45ad2eb991258c", "source_path": "desktop-ui/emulator/mega-cd.cpp"},
        {"system": "Mega CD", "name": "BIOS", "region": "Japan", "sha256": "7133fc2dd2fe5b7d0acd53a5f10f3d00b5d31270239ad20d74ef32393e24af88", "source_path": "desktop-ui/emulator/mega-cd.cpp"},
        {"system": "Mega CD", "name": "BIOS", "region": "Europe", "sha256": "fe608a2a07676a23ab5fd5eee2f53c9e2526d69a28aa16ccd85c0ec42e6933cb", "source_path": "desktop-ui/emulator/mega-cd.cpp"},
        {"system": "Game Gear", "name": "BIOS", "region": "World", "sha256": "8c8a21335038285cfa03dc076100c1f0bfadf3e4ff70796f11f3dfaaab60eee2", "source_path": "desktop-ui/emulator/game-gear.cpp"},
        {"system": "PC Engine CD", "name": "System-Card 1.0", "region": "Japan", "sha256": "afe9f27f91ac918348555b86298b4f984643eafa2773196f2c5441ea84f0c3bb", "source_path": "desktop-ui/emulator/pc-engine-cd.cpp"},
        {"system": "PC Engine CD", "name": "System Card 3.0", "region": "Japan", "sha256": "e11527b3b96ce112a037138988ca72fd117a6b0779c2480d9e03eaebece3d9ce", "source_path": "desktop-ui/emulator/pc-engine-cd.cpp"},
        {"system": "PC Engine CD", "name": "System Card 3.0", "region": "US", "sha256": "cadac2725711b3c442bcf237b02f5a5210c96f17625c35fa58f009e0ed39e4db", "source_path": "desktop-ui/emulator/pc-engine-cd.cpp"},
        {"system": "PC Engine CD", "name": "Games Express", "region": "Japan", "sha256": "4b86bb96a48a4ca8375fc0109631d0b1d64f255a03b01de70594d40788ba6c3d", "source_path": "desktop-ui/emulator/pc-engine-cd.cpp"},
        {"system": "LaserActive (NEC PAC)", "name": "PAC-N10", "region": "US", "sha256": "0e87a3385a27b3a4cac51934819b7eefa5b3d690768d2495633838488cd0e2e4", "source_path": "desktop-ui/emulator/pc-engine-ld.cpp"},
        {"system": "LaserActive (NEC PAC)", "name": "PAC-N1", "region": "Japan", "sha256": "459325690a458baebd77495c91e37c4dddfdd542ba13a821ce954e5bb245627f", "source_path": "desktop-ui/emulator/pc-engine-ld.cpp"},
        {"system": "LaserActive (NEC PAC)", "name": "PCE-LP1", "region": "Japan", "sha256": "3f43b3b577117d84002e99cb0baeb97b0d65b1d70b4adadc68817185c6a687f0", "source_path": "desktop-ui/emulator/pc-engine-ld.cpp"},
        {"system": "LaserActive (NEC PAC)", "name": "System-Card 1.0", "region": "Japan", "sha256": "afe9f27f91ac918348555b86298b4f984643eafa2773196f2c5441ea84f0c3bb", "source_path": "desktop-ui/emulator/pc-engine-ld.cpp"},
        {"system": "LaserActive (NEC PAC)", "name": "Games Express", "region": "Japan", "sha256": "4b86bb96a48a4ca8375fc0109631d0b1d64f255a03b01de70594d40788ba6c3d", "source_path": "desktop-ui/emulator/pc-engine-ld.cpp"},
        {"system": "Master System", "name": "BIOS", "region": "US", "sha256": "477617917a12a30f9f43844909dc2de6e6a617430f5c9a36306c86414a670d50", "source_path": "desktop-ui/emulator/master-system.cpp"},
        {"system": "Master System", "name": "BIOS", "region": "Japan", "sha256": "67846e26764bd862f19179294347f7353a4166b62ac4198a5ec32933b7da486e", "source_path": "desktop-ui/emulator/master-system.cpp"},
        {"system": "Master System", "name": "BIOS", "region": "Europe", "sha256": "477617917a12a30f9f43844909dc2de6e6a617430f5c9a36306c86414a670d50", "source_path": "desktop-ui/emulator/master-system.cpp"},
        {"system": "LaserActive (SEGA PAC)", "name": "BIOS", "region": "US", "sha256": "e89b5a319f66406611ec82fe5c4aa6827c175a05135bd7bd177366cba0465021", "source_path": "desktop-ui/emulator/mega-ld.cpp"},
        {"system": "LaserActive (SEGA PAC)", "name": "BIOS", "region": "Japan", "sha256": "dca942d977217f703d8d1c6eb1aeb6b32c78ecc421486bbb46c459d385161c94", "source_path": "desktop-ui/emulator/mega-ld.cpp"},
        {"system": "SuperGrafx CD", "name": "Arcade Card", "region": "Japan", "sha256": "e11527b3b96ce112a037138988ca72fd117a6b0779c2480d9e03eaebece3d9ce", "source_path": "desktop-ui/emulator/supergrafx-cd.cpp"},
        {"system": "PlayStation", "name": "BIOS", "region": "US", "sha256": "11052b6499e466bbf0a709b1f9cb6834a9418e66680387912451e971cf8a1fef", "source_path": "desktop-ui/emulator/playstation.cpp"},
        {"system": "PlayStation", "name": "BIOS", "region": "Japan", "sha256": "9c0421858e217805f4abe18698afea8d5aa36ff0727eb8484944e00eb5e7eadb", "source_path": "desktop-ui/emulator/playstation.cpp"},
        {"system": "PlayStation", "name": "BIOS", "region": "Europe", "sha256": "1faaa18fa820a0225e488d9f086296b8e6c46df739666093987ff7d8fd352c09", "source_path": "desktop-ui/emulator/playstation.cpp"},
        {"system": "Neo Geo Pocket", "name": "BIOS", "region": "World", "sha256": "0293555b21c4fac516d25199df7809b26beeae150e1d4504a050db32264a6ad7", "source_path": "desktop-ui/emulator/neo-geo-pocket.cpp"},
        {"system": "Neo Geo AES", "name": "BIOS", "region": "World", "source_path": "desktop-ui/emulator/neo-geo-aes.cpp"},
        {"system": "Neo Geo MVS", "name": "BIOS", "region": "World", "source_path": "desktop-ui/emulator/neo-geo-mvs.cpp"},
        {"system": "Nintendo 64DD", "name": "BIOS", "region": "Japan", "sha256": "806400ec0df94b0755de6c5b8249d6b6a9866124c5ddbdac198bde22499bfb8b", "source_path": "desktop-ui/emulator/nintendo-64dd.cpp"},
        {"system": "Nintendo 64DD", "name": "BIOS", "region": "US", "sha256": "e9fec87a45fba02399e88064b9e2f8cf0f2106e351c58279a87f05da5bc984ad", "source_path": "desktop-ui/emulator/nintendo-64dd.cpp"},
        {"system": "Nintendo 64DD", "name": "BIOS", "region": "DEV", "sha256": "9c2962a8b994a29e4cd04b3a6e4ed730a751414655ab6a9799ebf5fc08b79d44", "source_path": "desktop-ui/emulator/nintendo-64dd.cpp"},
        {"system": "Neo Geo Pocket Color", "name": "BIOS", "region": "World", "sha256": "8fb845a2f71514cec20728e2f0fecfade69444f8d50898b92c2259f1ba63e10d", "source_path": "desktop-ui/emulator/neo-geo-pocket-color.cpp"},
        {"system": "ColecoVision", "name": "BIOS", "region": "World", "sha256": "990bf1956f10207d8781b619eb74f89b00d921c8d45c95c334c16c8cceca09ad", "source_path": "desktop-ui/emulator/colecovision.cpp"},
        {"system": "Game Boy Advance", "name": "BIOS", "region": "World", "sha256": "fd2547724b505f487e6dcb29ec2ecff3af35a841a77ab2e85fd87350abd36570", "source_path": "desktop-ui/emulator/game-boy-advance.cpp"},
        {"system": "Atari 5200", "name": "BIOS", "region": "NTSC-U Four-port", "sha256": "06b250f18983d058c0f156ce7ee88ae48b6eaf11e6f10f21dccf6ac7ffb6a6af", "source_path": "desktop-ui/emulator/atari-5200.cpp"},
        {"system": "MSX", "name": "BIOS", "region": "Japan", "sha256": "413a2b601a94b3792e054be2439cc77a1819cceadbfa9542f88d51c7480f2ef0", "source_path": "desktop-ui/emulator/msx.cpp"},
        {"system": "Famicom Disk System", "name": "BIOS", "region": "Japan", "sha256": "fdc1a76e654feea993fcb38366e05ee5f4eb641f86fe6bebaeefd412e112dd72", "source_path": "desktop-ui/emulator/famicom-disk-system.cpp"},
    )

    PROFILE_ALIASES = {
        "super_zsnes": ("superzsnes",),
        "rmg": ("mupen64plus_next", "mupen64plus_next_develop"),
        "ryujinx_nextendo": ("ryujinx",),
        "xenia_canary": ("xenia",),
        "dosbox_staging": ("dosbox-staging",),
        "dosbox_x": ("dosbox-x",),
    }

    @classmethod
    def _read_firmware_assignments(
        cls, settings_path: str | Path
    ) -> tuple[AresUnassignedFirmware, ...]:
        """Lê todas as atribuições Emulator/Firmware do settings.bml do ARES."""
        path = Path(settings_path).expanduser()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise AresFirmwareError(f"Não foi possível ler o settings.bml do ares: {exc}") from exc

        parents: list[tuple[int, str]] = []
        assignments: list[AresUnassignedFirmware] = []
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
            emulator = ancestors[firmware_index - 1]
            firmware_type, region = identity
            location = raw_location.strip().strip('"')
            assignments.append(AresUnassignedFirmware(emulator, firmware_type, region, location))
        return tuple(assignments)

    @classmethod
    def read_firmware_assignments(
        cls, settings_path: str | Path
    ) -> tuple[AresUnassignedFirmware, ...]:
        """Retorna todas as atribuições de firmware declaradas pelo ARES."""
        return cls._read_firmware_assignments(settings_path)

    @classmethod
    def configured_settings_path(cls) -> Path | None:
        """Localiza o settings.bml do ARES configurado no SERM."""
        paths_file = data_root() / "emulator_paths.json"
        try:
            payload = json.loads(paths_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        raw = payload.get("ares_config") if isinstance(payload, dict) else None
        path = Path(raw).expanduser() if isinstance(raw, str) and raw.strip() else None
        return path if path is not None and path.is_file() else None

    @classmethod
    def scan_configured(
        cls,
        settings_path: str | Path,
        entries: tuple[AresFirmwareEntry, ...],
        *,
        catalog_version: str = "unknown",
    ) -> AresFirmwareScan:
        """Valida exatamente os arquivos atribuídos pelo ARES no settings.bml."""
        settings = Path(settings_path).expanduser().resolve()
        assignments = cls._read_firmware_assignments(settings)
        matches: dict[str, AresFirmwareMatch] = {}
        invalid: dict[str, AresFirmwareMatch] = {}

        def assignment_for(entry: AresFirmwareEntry, assignment: AresUnassignedFirmware) -> bool:
            return (
                entry.system.casefold() == assignment.emulator.casefold()
                and entry.name.replace(" ", "-").casefold() == assignment.firmware_type.casefold()
                and entry.region.casefold() == assignment.region.casefold()
            )

        for assignment in assignments:
            candidates = [entry for entry in entries if assignment_for(entry, assignment)]
            for entry in candidates:
                if not assignment.location:
                    continue
                location = Path(assignment.location).expanduser()
                if not location.is_absolute():
                    location = settings.parent / location
                if not location.is_file():
                    continue
                try:
                    identity = (
                        cls._hash_first_zip_member(location)
                        if location.suffix.casefold() == ".zip"
                        else cls._hash_file(location)
                    )
                except (OSError, zipfile.BadZipFile, RuntimeError):
                    continue
                if not entry.is_verifiable:
                    matches[entry.key] = AresFirmwareMatch(
                        entry, str(location), None, "configured"
                    )
                elif cls._matches_entry(identity, entry):
                    matches[entry.key] = AresFirmwareMatch(
                        entry, str(location), None, "hash"
                    )
                else:
                    invalid[entry.key] = AresFirmwareMatch(
                        entry, str(location), None, "invalid"
                    )

        missing = tuple(
            entry
            for entry in entries
            if entry.key not in matches and entry.key not in invalid
        )
        return AresFirmwareScan(
            catalog_version,
            str(settings),
            tuple(matches.values()),
            missing,
            sum(1 for assignment in assignments if assignment.location),
            tuple(invalid.values()),
            "ares",
        )

    @classmethod
    def _hash_first_zip_member(cls, path: Path) -> dict[str, object]:
        with zipfile.ZipFile(path) as archive:
            member = next((item for item in archive.infolist() if not item.is_dir()), None)
            if member is None:
                raise zipfile.BadZipFile(f"ZIP sem arquivos: {path}")
            with archive.open(member, "r") as stream:
                return cls._hash_stream(stream)

    @classmethod
    def read_unassigned_firmware(
        cls, settings_path: str | Path
    ) -> tuple[AresUnassignedFirmware, ...]:
        """Retorna somente atribuições de firmware sem arquivo existente."""
        assignments = cls._read_firmware_assignments(settings_path)
        settings = Path(settings_path).expanduser().resolve()
        missing: list[AresUnassignedFirmware] = []
        for assignment in assignments:
            if not assignment.location:
                missing.append(assignment)
                continue
            location = Path(assignment.location).expanduser()
            if not location.is_absolute():
                location = settings.parent / location
            if not location.is_file():
                missing.append(assignment)
        return tuple(missing)

    @classmethod
    def load_catalog(
        cls, *, emulator: str = "ares", refresh: bool = False
    ) -> tuple[str, tuple[AresFirmwareEntry, ...]]:
        source_entries = cls._ares_source_entries() if emulator.casefold() == "ares" else ()
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
            if source_entries:
                return f"ARES source {cls.ARES_SOURCE_REVISION}", source_entries
            raise AresFirmwareError(
                f"O RetroBIOS não possui perfil com arquivos para '{emulator}'."
            )

        if source_entries:
            # O ARES é a autoridade primária para seus próprios firmwares.
            # O RetroBIOS continua sendo usado apenas para enriquecer origem,
            # disponibilidade e lacunas de cobertura.
            entries = cls._merge_ares_source_entries(entries)
            try:
                database = cls.load_database(refresh=refresh)
                entries = cls._enrich_entries_from_database(entries, database)
            except AresFirmwareError:
                pass
            try:
                gaps = cls.load_gaps(refresh=refresh)
                entries = cls._enrich_entries_from_gaps(entries, gaps)
            except AresFirmwareError:
                pass
            return f"ARES source {cls.ARES_SOURCE_REVISION}", entries

        database = cls.load_database(refresh=refresh)
        entries = cls._enrich_entries_from_database(entries, database)
        gaps = cls.load_gaps(refresh=refresh)
        entries = cls._enrich_entries_from_gaps(entries, gaps)
        return version, entries

    @classmethod
    def _ares_source_entries(cls) -> tuple[AresFirmwareEntry, ...]:
        """Constrói o catálogo autoritativo a partir das declarações do ARES."""
        entries: list[AresFirmwareEntry] = []
        for item in cls.ARES_SOURCE_FIRMWARE:
            entries.append(
                AresFirmwareEntry(
                    name=item["name"],
                    system=item["system"],
                    description=f"ARES source: {item.get('region', '')}".rstrip(),
                    required=True,
                    sha256=item.get("sha256", ""),
                    output_path=item["name"],
                    profile_id="ares-source",
                    container_name=item.get("container_name", ""),
                    archive_required=False,
                    region=item.get("region", ""),

                )
            )
        return tuple(entries)

    @classmethod
    def _merge_ares_source_entries(
        cls, entries: tuple[AresFirmwareEntry, ...]
    ) -> tuple[AresFirmwareEntry, ...]:
        """Mescla o RetroBIOS sem deixar que ele substitua a definição do ARES."""
        source_entries = cls._ares_source_entries()
        merged = list(entries)
        for source_entry in source_entries:
            same_identity = next(
                (
                    index
                    for index, entry in enumerate(merged)
                    if (
                        (
                            entry.system.casefold() == source_entry.system.casefold()
                            and entry.name.casefold() == source_entry.name.casefold()
                            and entry.region.casefold() == source_entry.region.casefold()
                        )
                        or (
                            source_entry.sha256
                            and entry.sha256.casefold() == source_entry.sha256.casefold()
                            and (
                                not entry.region
                                or entry.region.casefold() == source_entry.region.casefold()
                            )
                        )
                    )
                ),
                None,
            )
            if same_identity is None:
                merged.append(source_entry)
                continue
            existing = merged[same_identity]
            merged[same_identity] = AresFirmwareEntry(
                name=source_entry.name,
                system=source_entry.system,
                description=source_entry.description,
                required=source_entry.required,
                sha256=source_entry.sha256 or existing.sha256,
                size=existing.size,
                sha1=existing.sha1,
                md5=existing.md5,
                crc32=existing.crc32,
                validation=existing.validation,
                output_path=existing.output_path or source_entry.output_path,
                aliases=existing.aliases,
                profile_id=source_entry.profile_id,
                repository_path=existing.repository_path,
                release_asset=existing.release_asset,
                catalog_available=existing.catalog_available,
                gap_layer=existing.gap_layer,
                gap_status=existing.gap_status,
                gap_in_repo=existing.gap_in_repo,
                gap_reason=existing.gap_reason,
                container_name=source_entry.container_name or existing.container_name,
                archive_required=source_entry.archive_required,
                region=source_entry.region or existing.region,
            )
        return tuple(merged)

    @classmethod
    def load_database(cls, *, refresh: bool = False) -> object:
        """Carrega o banco de conteúdo do RetroBIOS para complementar os perfis."""
        payload: object | None = None
        if refresh:
            try:
                request = urllib.request.Request(
                    cls.DATABASE_URL,
                    headers={"User-Agent": "SERM/2.x", "Accept": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=60) as response:
                    raw = response.read(cls.MAX_DATABASE_BYTES + 1)
                if len(raw) > cls.MAX_DATABASE_BYTES:
                    raise AresFirmwareError(
                        "O banco de conteúdo RetroBIOS ultrapassou o limite de 32 MiB."
                    )
                payload = json.loads(raw.decode("utf-8"))
                cls.DATABASE_CACHE.parent.mkdir(parents=True, exist_ok=True)
                cls.DATABASE_CACHE.write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
            except AresFirmwareError:
                raise
            except Exception as exc:  # noqa: BLE001
                if cls.DATABASE_CACHE.is_file():
                    payload = cls._read_database_cache()
                else:
                    raise AresFirmwareError(
                        f"Não foi possível atualizar o banco de conteúdo RetroBIOS: {exc}"
                    ) from exc
        else:
            payload = cls._read_database_cache()
            if payload is None:
                return cls.load_database(refresh=True)

        if payload is None:
            raise AresFirmwareError("O banco de conteúdo RetroBIOS não retornou dados.")
        return payload

    @classmethod
    def load_gaps(cls, *, refresh: bool = False) -> object:
        """Carrega as lacunas de cobertura publicadas pelo RetroBIOS."""
        payload: object | None = None
        if refresh:
            try:
                request = urllib.request.Request(
                    cls.GAPS_URL,
                    headers={"User-Agent": "SERM/2.x", "Accept": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    raw = response.read(cls.MAX_GAPS_BYTES + 1)
                if len(raw) > cls.MAX_GAPS_BYTES:
                    raise AresFirmwareError(
                        "O banco de lacunas RetroBIOS ultrapassou o limite de 8 MiB."
                    )
                payload = json.loads(raw.decode("utf-8"))
                cls.GAPS_CACHE.parent.mkdir(parents=True, exist_ok=True)
                cls.GAPS_CACHE.write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
            except AresFirmwareError:
                raise
            except Exception as exc:  # noqa: BLE001
                if cls.GAPS_CACHE.is_file():
                    payload = cls._read_gaps_cache()
                else:
                    raise AresFirmwareError(
                        f"Não foi possível atualizar as lacunas RetroBIOS: {exc}"
                    ) from exc
        else:
            payload = cls._read_gaps_cache()
            if payload is None:
                return cls.load_gaps(refresh=True)
        if payload is None:
            raise AresFirmwareError("O banco de lacunas RetroBIOS não retornou dados.")
        return payload

    @classmethod
    def _enrich_entries_from_gaps(
        cls,
        entries: tuple[AresFirmwareEntry, ...],
        gaps: object,
    ) -> tuple[AresFirmwareEntry, ...]:
        """Relaciona somente lacunas da camada de emulador aos arquivos do perfil."""
        records = cls._gap_records(gaps)
        by_name: dict[str, list[dict[str, object]]] = {}
        for record in records:
            for name in cls._gap_names(record):
                by_name.setdefault(name, []).append(record)

        enriched: list[AresFirmwareEntry] = []
        for entry in entries:
            candidates: list[dict[str, object]] = []
            names = {Path(entry.name).name.casefold(), Path(entry.output_path).name.casefold()}
            names.update(Path(alias).name.casefold() for alias in entry.aliases)
            for name in names:
                candidates.extend(by_name.get(name, ()))
            candidate = next(
                (
                    record for record in candidates
                    if cls._gap_matches_entry(record, entry)
                ),
                None,
            )
            if candidate is None:
                enriched.append(entry)
                continue
            enriched.append(
                AresFirmwareEntry(
                    name=entry.name,
                    system=entry.system,
                    description=entry.description,
                    required=entry.required,
                    sha256=entry.sha256,
                    size=entry.size,
                    sha1=entry.sha1,
                    md5=entry.md5,
                    crc32=entry.crc32,
                    validation=entry.validation,
                    output_path=entry.output_path,
                    aliases=entry.aliases,
                    profile_id=entry.profile_id,
                    repository_path=entry.repository_path,
                    release_asset=entry.release_asset,
                    catalog_available=entry.catalog_available,
                    gap_layer="emulator",
                    gap_status=str(candidate.get("status") or "").strip(),
                    gap_in_repo=(bool(candidate.get("in_repo")) if "in_repo" in candidate else None),
                    gap_reason=str(candidate.get("reason") or "").strip(),
                    container_name=entry.container_name,
                    archive_required=entry.archive_required,
                )
            )
        return tuple(enriched)

    @staticmethod
    def _gap_records(payload: object) -> tuple[dict[str, object], ...]:
        if not isinstance(payload, dict):
            return ()
        items = payload.get("items")
        if not isinstance(items, list):
            return ()
        return tuple(
            item for item in items
            if isinstance(item, dict) and str(item.get("layer") or "").casefold() == "emulator"
        )

    @staticmethod
    def _gap_names(record: dict[str, object]) -> tuple[str, ...]:
        value = record.get("name")
        if not isinstance(value, str) or not value.strip():
            return ()
        return (Path(value).name.casefold(),)

    @staticmethod
    def _gap_matches_entry(record: dict[str, object], entry: AresFirmwareEntry) -> bool:
        system = str(record.get("system") or "").strip().casefold()
        if not system:
            return True
        entry_systems = {part.strip().casefold() for part in entry.system.split(";") if part.strip()}
        return system in entry_systems

    @classmethod
    def _enrich_entries_from_database(
        cls,
        entries: tuple[AresFirmwareEntry, ...],
        database: object,
    ) -> tuple[AresFirmwareEntry, ...]:
        """Relaciona perfis de emulador ao conteúdo disponível no banco RetroBIOS."""
        records = cls._database_records(database)
        by_identity: dict[tuple[str, str], dict[str, object]] = {}
        by_name: dict[str, dict[str, object]] = {}

        for record in records:
            for algorithm in ("sha256", "sha1", "md5", "crc32"):
                digest = str(record.get(algorithm) or "").casefold()
                if digest:
                    by_identity[(algorithm, digest)] = record
            for name in cls._record_names(record):
                if name:
                    by_name.setdefault(name, record)

        enriched: list[AresFirmwareEntry] = []
        for entry in entries:
            record = None
            for algorithm in ("sha256", "sha1", "md5", "crc32"):
                digest = getattr(entry, algorithm)
                if digest:
                    record = by_identity.get((algorithm, digest.casefold()))
                    if record:
                        break
            if record is None:
                names = {Path(entry.name).name.casefold(), Path(entry.output_path).name.casefold()}
                names.update(Path(alias).name.casefold() for alias in entry.aliases)
                for name in names:
                    record = by_name.get(name)
                    if record:
                        break

            if record is None:
                enriched.append(entry)
                continue

            repository_path = str(record.get("repo_path") or record.get("path") or "").strip()
            release_asset = str(record.get("release_asset") or "").strip()
            enriched.append(
                AresFirmwareEntry(
                    name=entry.name,
                    system=entry.system,
                    description=entry.description,
                    required=entry.required,
                    sha256=entry.sha256,
                    size=entry.size,
                    sha1=entry.sha1,
                    md5=entry.md5,
                    crc32=entry.crc32,
                    validation=entry.validation,
                    output_path=entry.output_path,
                    aliases=entry.aliases,
                    profile_id=entry.profile_id,
                    repository_path=repository_path,
                    release_asset=release_asset,
                    catalog_available=bool(repository_path or release_asset),
                    container_name=entry.container_name,
                    archive_required=entry.archive_required,
                )
            )
        return tuple(enriched)

    @staticmethod
    def _database_records(payload: object) -> tuple[dict[str, object], ...]:
        """Extrai registros de arquivo de versões v1 sem depender do índice interno."""
        records: list[dict[str, object]] = []

        def visit(value: object) -> None:
            if isinstance(value, dict):
                has_identity = any(
                    str(value.get(key) or "").strip()
                    for key in ("sha256", "sha1", "md5", "crc32")
                )
                has_location = any(
                    str(value.get(key) or "").strip()
                    for key in ("repo_path", "release_asset", "path")
                )
                if has_identity and has_location:
                    records.append(value)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(payload)
        return tuple(records)

    @staticmethod
    def _record_names(record: dict[str, object]) -> tuple[str, ...]:
        names: list[str] = []
        for key in ("name", "filename", "file", "dest", "path", "repo_path"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                names.append(Path(value).name.casefold())
        return tuple(dict.fromkeys(names))

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
                    cls._scan_zip(candidate, hash_index, name_index, found, root)
                else:
                    identity = cls._hash_file(candidate)
                    cls._record_matches(hash_index, name_index, identity, candidate, None, found, root)
            except (OSError, zipfile.BadZipFile, RuntimeError):
                pass
            examined += 1
            if progress_callback:
                progress_callback(examined, total)

        matches = tuple(found[key] for key in sorted(found))
        matched_names = set(found)
        missing = tuple(entry for entry in entries if entry.key not in matched_names)
        return AresFirmwareScan(
            catalog_version,
            str(root),
            matches,
            missing,
            examined,
            emulator=emulator,
        )

    @classmethod
    def write_filter_file(
        cls, scan: AresFirmwareScan, selected: tuple[AresFirmwareMatch, ...]
    ) -> Path:
        """Write SERM reconstruction input for the selected firmware matches."""
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
        root: Path,
    ) -> None:
        archive_identity = cls._hash_file(path)
        cls._record_matches(hash_index, name_index, archive_identity, path, None, found, root)
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                with archive.open(member, "r") as stream:
                    identity = cls._hash_stream(stream)
                cls._record_matches(hash_index, name_index, identity, path, member.filename, found, root)

                archive_name = path.name.casefold()
                member_name = Path(member.filename).name.casefold()
                for entry in name_index.get(member_name, ()):
                    if (
                        entry.container_name
                        and Path(entry.container_name).name.casefold() == archive_name
                    ):
                        existing = found.get(entry.key)
                        if existing is None:
                            found[entry.key] = AresFirmwareMatch(
                                entry, str(path), member.filename, "archive"
                            )
                        elif (
                            existing.archive_member == member.filename
                            and existing.match_mode == "name"
                        ):
                            found[entry.key] = AresFirmwareMatch(
                                entry, str(path), member.filename, "archive"
                            )

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
        """Indexa todos os nomes para fallback quando não houver hash compatível."""
        index: dict[str, list[AresFirmwareEntry]] = {}
        for entry in entries:
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
        root: Path | None = None,
    ) -> None:
        candidates: dict[str, AresFirmwareEntry] = {}
        for algorithm in ("sha256", "sha1", "md5", "crc32"):
            digest = str(identity.get(algorithm) or "").casefold()
            for entry in hash_index.get((algorithm, digest), ()):
                candidates[entry.key] = entry

        def allowed(entry: AresFirmwareEntry) -> bool:
            if entry.profile_id == "ares-source":
                # O ARES não define nome de arquivo para seu firmware. Entradas
                # sem SHA-256 só podem ser validadas pela atribuição do settings.bml.
                if not entry.is_verifiable:
                    return False
                return cls._matches_entry(identity, entry) and (
                    member is None
                    or Path(member).name.casefold() == Path(entry.name).name.casefold()
                )
            if entry.archive_required:
                if member is None or Path(entry.container_name).name.casefold() != path.name.casefold():
                    return False
                return Path(member).name.casefold() == Path(entry.name).name.casefold()
            expected = PurePosixPath(entry.output_path.replace("\\", "/"))
            if len(expected.parts) <= 1:
                return True
            if member is not None:
                return PurePosixPath(member.replace("\\", "/")) == expected
            if root is None:
                return True
            try:
                actual = PurePosixPath(path.relative_to(root).as_posix())
            except ValueError:
                return False
            return actual == expected

        hash_matches = [
            entry for entry in candidates.values()
            if entry.key not in found and allowed(entry) and cls._matches_entry(identity, entry)
        ]
        for entry in hash_matches:
            found[entry.key] = AresFirmwareMatch(entry, str(path), member, "hash")

        # O hash sempre tem precedência. Se nenhum hash do arquivo coincidir,
        # aceita a mesma nomenclatura como fallback, inclusive para entradas
        # que possuem hash no catálogo. Isso permite usar um dump com nome
        # reconhecido quando o catálogo não oferece uma identidade coincidente.
        if hash_matches:
            return
        member_name = Path(member).name.casefold() if member else path.name.casefold()
        for entry in name_index.get(member_name, ()):
            if entry.key not in found and allowed(entry):
                found[entry.key] = AresFirmwareMatch(entry, str(path), member, "name")

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
                system = str(item.get("system") or profile.get("display_name") or profile_id)
                container_name = str(
                    item.get("container_name")
                    or item.get("archive_name")
                    or item.get("archive")
                    or item.get("container")
                    or ""
                ).strip()
                catalog_container_name = container_name
                if (
                    not container_name
                    and target == "ares"
                    and system.casefold() == "neo-geo"
                    and name.casefold() in {"neo-epo.bin", "sp-45.sp1"}
                ):
                    container_name = "neogeo.zip"
                archive_required = bool(catalog_container_name)
                entry = AresFirmwareEntry(
                    name=name,
                    system=system,
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
                    container_name=container_name,
                    archive_required=archive_required,
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
    def _read_gaps_cache(cls) -> object | None:
        try:
            if cls.GAPS_CACHE.stat().st_size > cls.MAX_GAPS_BYTES:
                return None
            return json.loads(cls.GAPS_CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None

    @classmethod
    def _read_database_cache(cls) -> object | None:
        try:
            if cls.DATABASE_CACHE.stat().st_size > cls.MAX_DATABASE_BYTES:
                return None
            return json.loads(cls.DATABASE_CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None

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