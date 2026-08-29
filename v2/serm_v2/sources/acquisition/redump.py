"""Direct Redump DAT acquisition backend for SERM."""
from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import unicodedata
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote

logger = logging.getLogger(__name__)


class RedumpError(RuntimeError):
    """Raised when a Redump direct DAT download cannot be consumed."""


@dataclass(frozen=True, slots=True)
class RedumpEntry:
    """Describe a Redump system and its direct DAT endpoint."""

    name: str
    code: str
    url: str
    category: str = "Redump"


@dataclass(frozen=True, slots=True)
class RedumpStatus:
    """Describe the local state of a Redump DAT."""

    entry: RedumpEntry
    path: Path
    state: str
    sha256: str | None = None


class RedumpProvider:
    """Download Redump DAT ZIPs through their direct per-system endpoints.

    The endpoint pattern is ``/datfile/<system-code>/``.  This avoids the
    interactive downloads page and therefore does not require Selenium,
    CAPTCHA handling, or account authentication.
    """

    BASE_URLS = (
        "https://redump.info",
        "http://redump.org",
    )
    USER_AGENT = "SERM/2.0"

    SYSTEM_CODES = {
        "Acorn - Archimedes": "arch",
        "Apple - Macintosh": "mac",
        "Arcade - Konami - e-Amusement": "kea",
        "Arcade - Konami - FireBeat": "kfb",
        "Arcade - Konami - System GV": "ksgv",
        "Arcade - Namco - Sega - Nintendo - Triforce": "trf",
        "Arcade - Sega - Chihiro": "chihiro",
        "Arcade - Sega - Lindbergh": "lindbergh",
        "Arcade - Sega - Naomi": "naomi",
        "Arcade - Sega - Naomi 2": "naomi2",
        "Arcade - Sega - RingEdge": "sre",
        "Arcade - Sega - RingEdge 2": "sre2",
        "Atari - Jaguar CD Interactive Multimedia System": "ajcd",
        "Bandai - Pippin": "pippin",
        "Bandai - Playdia Quick Interactive System": "qis",
        "Commodore - Amiga CD": "acd",
        "Commodore - Amiga CD32": "cd32",
        "Commodore - Amiga CDTV": "cdtv",
        "Fujitsu - FM-Towns": "fmt",
        "funworld - Photo Play": "fpp",
        "IBM - PC compatible": "pc",
        "Incredible Technologies - Eagle": "ite",
        "Mattel - Fisher-Price iXL": "ixl",
        "Mattel - HyperScan": "hs",
        "Memorex - Visual Information System": "vis",
        "Microsoft - Xbox": "xbox",
        "Microsoft - Xbox 360": "xbox360",
        "NEC - PC Engine CD & TurboGrafx CD": "pce",
        "NEC - PC-88 series": "pc-88",
        "NEC - PC-98 series": "pc-98",
        "NEC - PC-FX & PC-FXGA": "pc-fx",
        "Nintendo - GameCube": "gc",
        "Nintendo - Wii": "wii",
        "Palm": "palm",
        "Panasonic - 3DO Interactive Multiplayer": "3do",
        "Philips - CD-i": "cdi",
        "Photo CD": "photo-cd",
        "PlayStation GameShark Updates": "psxgs",
        "Sega - Dreamcast": "dc",
        "Sega - Mega CD & Sega CD": "mcd",
        "Sega - Prologue 21": "sp21",
        "Sega - Saturn": "ss",
        "SNK - Neo Geo CD": "ngcd",
        "Sony - PlayStation": "psx",
        "Sony - PlayStation 2": "ps2",
        "Sony - PlayStation 3": "ps3",
        "Sony - PlayStation Portable": "psp",
        "TAB-Austria - Quizard": "quizard",
        "Tomy - Kiss-Site": "ksite",
        "VM Labs - NUON": "nuon",
        "VTech - V.Flash & V.Smile Pro": "vflash",
        "ZAPiT Games - Game Wave Family Entertainment System": "gamewave",
    }

    def __init__(self, *, root: Path | None = None, timeout: int = 60) -> None:
        """Initialize the Redump provider and local DAT directory."""
        self.root = Path(root).expanduser() if root else self._default_root()
        self.timeout = timeout
        self.manifest_path = self.root / "manifest.json"

    @staticmethod
    def _default_root() -> Path:
        """Return the repository-local Redump DAT directory."""
        return Path(__file__).resolve().parents[3] / "data" / "sources" / "redump" / "dats"

    def fetch_catalog(self) -> tuple[RedumpEntry, ...]:
        """Return every known Redump direct DAT endpoint."""
        return tuple(
            RedumpEntry(name=name, code=code, url=f"{self.BASE_URLS[0]}/datfile/{quote(code)}/")
            for name, code in sorted(self.SYSTEM_CODES.items())
        )

    def match(
        self,
        systems: tuple[str, ...],
        entries: tuple[RedumpEntry, ...] | None = None,
    ) -> tuple[RedumpEntry, ...]:
        """Match LaunchBox platform names against Redump system names."""
        entries = entries if entries is not None else self.fetch_catalog()
        keys = {self._normalize(system) for system in systems}
        keys.update(self._alias(value) for value in tuple(keys))
        return tuple(entry for entry in entries if self._normalize(entry.name) in keys)

    def destination(self, entry: RedumpEntry) -> Path:
        """Return the stable local DAT path for a Redump system."""
        safe = re.sub(r"[^A-Za-z0-9._()\- ]+", "", entry.name).strip()
        return self.root / f"{safe}.dat"

    def status(self, entry: RedumpEntry) -> RedumpStatus:
        """Return whether the DAT is present locally."""
        path = self.destination(entry)
        if not path.is_file():
            return RedumpStatus(entry=entry, path=path, state="missing")
        digest = self._sha256(path)
        return RedumpStatus(entry=entry, path=path, state="current", sha256=digest)

    def download(self, entry: RedumpEntry) -> RedumpStatus:
        """Download the direct Redump ZIP, extract exactly one DAT, and atomically save it."""
        destination = self.destination(entry)
        destination.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None

        for base_url in self.BASE_URLS:
            url = f"{base_url}/datfile/{quote(entry.code)}/"
            logger.info("[REDUMP][HTTP] GET %s", url)
            request = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = response.read()
                    status_code = getattr(response, "status", 200)
                    content_type = response.headers.get("Content-Type", "")
            except HTTPError as exc:
                last_error = exc
                logger.warning("[REDUMP][HTTP] %s respondeu HTTP %s", base_url, exc.code)
                continue
            except (URLError, OSError) as exc:
                last_error = exc
                logger.warning("[REDUMP][HTTP] falha em %s: %s", base_url, exc)
                continue

            logger.info(
                "[REDUMP][HTTP] resposta=%s bytes=%d content-type=%s",
                status_code,
                len(data),
                content_type or "unknown",
            )
            try:
                dat_name, dat_data = self._extract_dat(data)
            except RedumpError as exc:
                last_error = exc
                logger.warning("[REDUMP][DAT] %s", exc)
                continue

            partial = destination.with_suffix(".dat.part")
            partial.write_bytes(dat_data)
            partial.replace(destination)
            status = self.status(entry)
            self._write_manifest(entry, status, dat_name, url, hashlib.sha256(data).hexdigest())
            logger.info("[REDUMP][DAT] OK sistema=%s arquivo=%s", entry.name, destination)
            return status

        raise RedumpError(f"Falha ao obter DAT Redump '{entry.name}': {last_error}")

    @staticmethod
    def _extract_dat(payload: bytes) -> tuple[str, bytes]:
        """Extract exactly one DAT file from a Redump ZIP payload."""
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                names = [name for name in archive.namelist() if not name.endswith("/")]
                dat_names = [name for name in names if name.lower().endswith(".dat")]
                if len(dat_names) != 1 or len(names) != 1:
                    raise RedumpError(
                        f"ZIP Redump inválido: arquivos={len(names)} dats={len(dat_names)}"
                    )
                data = archive.read(dat_names[0])
        except zipfile.BadZipFile as exc:
            raise RedumpError("resposta não é um ZIP Redump válido") from exc
        if not data.lstrip().startswith(b"<"):
            raise RedumpError("arquivo extraído não parece ser um DAT XML")
        return Path(dat_names[0]).name, data

    def _write_manifest(
        self,
        entry: RedumpEntry,
        status: RedumpStatus,
        dat_name: str,
        url: str,
        archive_sha256: str,
    ) -> None:
        """Persist direct-source provenance and archive digest."""
        manifest: dict[str, dict[str, object]] = {}
        if self.manifest_path.is_file():
            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                manifest = {}
        manifest[entry.name] = {
            "code": entry.code,
            "url": url,
            "dat_name": dat_name,
            "sha256": status.sha256,
            "archive_sha256": archive_sha256,
        }
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        """Calculate the SHA-256 digest of a local DAT."""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize platform names for deterministic matching."""
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        value = value.casefold().replace("&", "and")
        return re.sub(r"[^a-z0-9]+", " ", value).strip()

    @classmethod
    def _alias(cls, value: str) -> str:
        """Map common LaunchBox platform aliases to Redump names."""
        aliases = {
            "playstation": "sony playstation",
            "playstation 2": "sony playstation 2",
            "playstation 3": "sony playstation 3",
            "psp": "sony playstation portable",
            "playstation portable": "sony playstation portable",
            "dreamcast": "sega dreamcast",
            "saturn": "sega saturn",
            "sega cd": "sega mega cd and sega cd",
            "mega cd": "sega mega cd and sega cd",
            "gamecube": "nintendo gamecube",
            "wii": "nintendo wii",
            "xbox": "microsoft xbox",
            "xbox 360": "microsoft xbox 360",
            "neo geo cd": "snk neo geo cd",
        }
        return aliases.get(value, value)
