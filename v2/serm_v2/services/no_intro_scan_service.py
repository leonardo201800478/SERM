"""Motor de scan No-Intro orientado a metadados e auditoria física."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import time
import zipfile
import zlib
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from ..runtime.paths import scans_root
from .rom_scan_service import ScanEvidence, ScanResult


class NoIntroScanError(RuntimeError):
    """Erro controlado do scanner No-Intro."""


@dataclass(slots=True, frozen=True)
class _ExpectedRom:
    game_name: str
    rom_name: str
    size: int
    crc: str
    md5: str
    sha1: str
    rom_status: str
    fmt: str
    cloneof: str | None
    base_name: str
    regions: tuple[str, ...]
    languages: tuple[str, ...]
    tags: tuple[str, ...]


class NoIntroScanService:
    """Audita um DAT No-Intro e produz um snapshot rico em metadados."""

    CHUNK_SIZE = 1024 * 1024
    VARIANT_STATUS = "UNVERIFIED_VARIANT"
    VARIANT_PATTERNS = (
        ("translation", re.compile(r"(?:translation|translated|trad(?:uced|ucao|ução)?|\[t[+\-][^\]]*\]|\(t[+\-][^)]*\))", re.I)),
        ("hack", re.compile(r"(?:hack|hacked|romhack|\[h[+\-][^\]]*\]|\(hack[^)]*\))", re.I)),
    )
    REGION_ALIASES = {
        "usa": "USA/America", "america": "USA/America", "us": "USA/America",
        "eur": "Europe", "europe": "Europe", "eu": "Europe",
        "jpn": "Japan", "japan": "Japan", "chn": "China", "china": "China", "cn": "China",
        "kor": "Korea", "korea": "Korea", "kr": "Korea", "spa": "Spain", "spain": "Spain",
        "esp": "Spain", "por": "Portugal", "portugal": "Portugal", "pt": "Portugal",
        "bra": "Brazil", "brazil": "Brazil", "br": "Brazil", "world": "World", "ww": "World",
    }
    LANGUAGE_CODES = {"En", "Fr", "De", "Es", "It", "Pt", "Nl", "Sv", "Da", "No", "Fi", "Ru", "Pl", "Cs", "Hu", "Tr", "El", "Ja", "Zh", "Ko", "Ar", "He", "Th", "Vi"}
    TYPE_TOKENS = {
        "bios": "type:bios", "program": "type:program", "beta": "type:beta", "proto": "type:proto",
        "prototype": "type:proto", "demo": "type:demo", "tech demo": "type:tech_demo", "techdemo": "type:tech_demo",
        "sample": "type:sample", "np": "type:np", "aftermarket": "type:aftermarket", "unl": "type:unlicensed",
        "unlicensed": "type:unlicensed", "pirate": "type:pirate", "enhancement chip": "type:enhancement_chip",
        "enhancementchip": "type:enhancement_chip",
    }

    def __init__(self, *, progress_callback: Callable[[int, int], None] | None = None) -> None:
        self.progress_callback = progress_callback
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def scan(self, profile) -> ScanResult:
        started = time.time()
        dat_path = self._resolve_dat_path(profile)
        sources = self._resolve_sources(profile)
        expected, header = self._load_dat(dat_path)
        if not expected:
            raise NoIntroScanError(f"Nenhuma ROM encontrada no DAT: {dat_path}")
        result = ScanResult(scan_id=self._make_scan_id(profile), profile_id=str(profile.profile_id), source="No-Intro", system=str(profile.system), started_at=started, catalog_label=f"{profile.system} - {self._catalog_label(dat_path, header)}", scan_type="full")
        result.catalog_hash = self._sha256(dat_path)
        stream_path = scans_root() / "streaming" / f"{result.scan_id}.jsonl"
        stream_path.parent.mkdir(parents=True, exist_ok=True)
        result.evidence_stream_path = str(stream_path)
        games = self._group_by_game(expected)
        total = len(expected)
        completed = 0
        known_bases = {self._normalize_name(item.base_name): item.base_name for item in expected}
        with stream_path.open("w", encoding="utf-8", newline="\n") as stream:
            self._write_jsonl(stream, {"record_type": "header", "format": "SERM-SCAN-V1", "scan_id": result.scan_id, "profile_id": result.profile_id, "source": result.source, "system": result.system, "scan_type": result.scan_type, "catalog_label": result.catalog_label, "catalog_hash": result.catalog_hash, "dat_path": str(dat_path), "started_at": started, "source_paths": [str(p) for p in sources], "machine_count_expected": len(games), "item_count_expected": total, "metadata": {"validation": "expected_driven", "persist_mode": "streaming", "filters_applied": False, "naming_convention": "No-Intro", "unverified_variants": True}})
            for game_name, items in games.items():
                if self._cancelled:
                    break
                self._scan_game(game_name, items, sources, result, stream)
                completed += len(items)
                if self.progress_callback:
                    self.progress_callback(completed, total)
                if completed == total or completed % 250 == 0:
                    stream.flush()
            if not self._cancelled:
                self._discover_unverified_variants(sources, known_bases, result, stream)
            self._write_jsonl(stream, {"record_type": "scan_end", "status": "cancelled" if self._cancelled else "completed", "finished_at": time.time(), "status_counts": dict(result.status_counts), "files_examined": result.files_examined, "archives_examined": result.archives_examined, "items_examined": result.items_examined, "errors": result.errors})
            stream.flush()
        result.finished_at = time.time()
        return result

    @staticmethod
    def _resolve_dat_path(profile) -> Path:
        path = Path(profile.dat_path).expanduser().resolve() if profile.dat_path else None
        if path is None or not path.is_file():
            raise NoIntroScanError("O perfil No-Intro não possui um DAT local válido.")
        return path

    @staticmethod
    def _resolve_sources(profile) -> list[Path]:
        sources = [Path(p).expanduser().resolve() for p in profile.source_directories]
        if not sources:
            raise NoIntroScanError("Nenhum diretório de origem foi configurado para o scan No-Intro.")
        for source in sources:
            if not source.is_dir():
                raise NoIntroScanError(f"Diretório de origem não encontrado: {source}")
        return sources

    def _scan_game(self, game_name, items, sources, result, stream) -> None:
        expected_by_name: dict[str, list[_ExpectedRom]] = {}
        for item in items:
            expected_by_name.setdefault(Path(item.rom_name).name.casefold(), []).append(item)
        occurrences: Counter[tuple[str, str, int, str]] = Counter()
        for source in sources:
            archive = source / f"{game_name}.zip"
            if archive.is_file():
                result.files_examined += 1
                result.archives_examined += 1
                self._scan_zip(archive, expected_by_name, occurrences, result, stream)
            for item in items:
                loose = source / Path(item.rom_name).name
                if loose.is_file():
                    result.files_examined += 1
                    self._scan_loose(loose, item, occurrences, result, stream)
        for item in items:
            if occurrences[self._item_key(item)] == 0:
                self._emit(self._evidence(item, "MISSING", message="Arquivo não encontrado na fonte do scan."), result, stream)

    def _scan_zip(self, archive, expected_by_name, occurrences, result, stream) -> None:
        try:
            with zipfile.ZipFile(archive) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    candidates = expected_by_name.get(Path(info.filename).name.casefold())
                    if not candidates:
                        continue
                    result.items_examined += 1
                    for item in candidates:
                        key = self._item_key(item)
                        duplicate = occurrences[key] > 0
                        evidence = self._validate_zip_member(zf, info, item, archive, duplicate=duplicate)
                        occurrences[key] += 1
                        self._emit(evidence, result, stream)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            result.errors += 1
            self._log_error(result, stream, archive, exc)

    def _scan_loose(self, path, item, occurrences, result, stream) -> None:
        key = self._item_key(item)
        try:
            size, crc, md5, sha1 = self._hash_file(path)
            status = self._compare(item, size, crc, md5, sha1)
            if status == "CURRENT" and occurrences[key] > 0:
                status = "DUPLICATE"
            occurrences[key] += 1
            self._emit(self._evidence(item, status, actual_size=size, actual_crc=crc, actual_md5=md5, actual_sha1=sha1, path=str(path)), result, stream)
        except OSError as exc:
            result.errors += 1
            self._log_error(result, stream, path, exc)

    def _validate_zip_member(self, zf, info, item, archive, *, duplicate: bool):
        size, crc, md5, sha1 = self._hash_zip_member_full(zf, info)
        status = self._compare(item, size, crc, md5, sha1)
        if status == "CURRENT" and duplicate:
            status = "DUPLICATE"
        return self._evidence(item, status, actual_size=size, actual_crc=crc, actual_md5=md5, actual_sha1=sha1, archive_path=str(archive), archive_member=info.filename)

    @staticmethod
    def _compare(item, size, crc, md5, sha1):
        if size != item.size or (item.crc and crc.casefold() != item.crc.casefold()) or (item.md5 and md5.casefold() != item.md5.casefold()) or (item.sha1 and sha1.casefold() != item.sha1.casefold()):
            return "WRONG"
        return "CURRENT"

    def _discover_unverified_variants(self, sources, known_bases, result, stream) -> None:
        for source in sources:
            for archive in source.glob("*.zip"):
                if self._cancelled:
                    return
                stem = archive.stem
                variant = self._variant_kind(stem)
                if not variant:
                    continue
                base = self._match_variant_base(stem, known_bases)
                if base is None:
                    continue
                try:
                    with zipfile.ZipFile(archive) as zf:
                        result.files_examined += 1
                        result.archives_examined += 1
                        for info in zf.infolist():
                            if info.is_dir():
                                continue
                            size, crc, md5, sha1 = self._hash_zip_member_full(zf, info)
                            tags = [f"variant:{variant}", "verification:unverified", "type:game"]
                            tags.extend(self._name_metadata(stem)["tags"])
                            evidence = ScanEvidence(machine_name=stem, rom_name=Path(info.filename).name, status=self.VARIANT_STATUS, actual_size=size, actual_crc=crc, actual_md5=md5, actual_sha1=sha1, archive_path=str(archive), archive_member=info.filename, merge_name=base, categories=tuple(dict.fromkeys(tags)), message=f"Variante externa {variant}; nome compatível com '{base}', sem hashes no DAT.")
                            self._emit(evidence, result, stream)
                            result.items_examined += 1
                except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
                    result.errors += 1
                    self._log_error(result, stream, archive, exc)

    def _match_variant_base(self, name, known_bases):
        normalized = self._normalize_name(name)
        if normalized in known_bases:
            return known_bases[normalized]
        best_name = None
        best_score = 0.0
        for candidate, original in known_bases.items():
            score = difflib.SequenceMatcher(None, normalized, candidate).ratio()
            if score > best_score:
                best_score, best_name = score, original
        return best_name if best_score >= 0.82 else None

    @classmethod
    def _variant_kind(cls, name):
        found = [kind for kind, pattern in cls.VARIANT_PATTERNS if pattern.search(name)]
        return "+".join(found) if found else None

    @classmethod
    def _parse_name(cls, game_name, rom_name, cloneof, rom_status="", fmt="", release_regions=()):
        parenthetical = re.findall(r"\(([^()]*)\)", game_name)
        square = re.findall(r"\[([^\]]*)\]", game_name)
        tokens = []
        for group in (*parenthetical, *square):
            tokens.extend([part.strip() for part in group.split(",") if part.strip()])
        regions = []
        languages = []
        tags = ["clone:yes" if cloneof else "clone:no"]
        lowered_name = game_name.casefold()
        if re.search(r"^\s*\[bios\]\b", lowered_name):
            tags.append("type:bios")
        if re.search(r"\[\s*b\s*\]", lowered_name) or re.search(r"\(\s*b\s*\)", lowered_name):
            tags.append("status:baddump")
        if rom_status:
            status = rom_status.casefold()
            tags.append(f"romstatus:{status}")
            if status in {"b", "bad", "bad dump", "baddump"}:
                tags.append("status:baddump")
        if fmt:
            tags.append(f"format:{fmt.casefold()}")
        for release_region in release_regions:
            region = cls.REGION_ALIASES.get(str(release_region).strip().casefold())
            if region:
                regions.append(region)
            elif str(release_region).strip():
                regions.append(str(release_region).strip())
        for token in tokens:
            lower = token.casefold().strip()
            region = cls.REGION_ALIASES.get(lower)
            if region:
                regions.append(region)
            normalized = re.sub(r"\s+", " ", lower)
            if token in cls.LANGUAGE_CODES:
                languages.append(token)
            if normalized in cls.TYPE_TOKENS:
                tags.append(cls.TYPE_TOKENS[normalized])
            compact = normalized.replace(" ", "")
            if compact in cls.TYPE_TOKENS:
                tags.append(cls.TYPE_TOKENS[compact])
            if lower.startswith("beta"):
                tags.append("type:beta")
            if lower.startswith("proto"):
                tags.append("type:proto")
            if lower.startswith("tech demo") or lower.startswith("techdemo"):
                tags.append("type:tech_demo")
            if lower.startswith("rev") or re.match(r"^v\d", lower):
                tags.append(f"version:{token}")
            if lower in {"b", "bad", "bad dump", "bad dump?"}:
                tags.append("status:baddump")
            if lower.startswith("t-") or lower.startswith("t+"):
                tags.append("variant:translation")
            if "translated" in lower or "translation" in lower or lower.startswith("trad ") or lower.startswith("trad-"):
                tags.append("variant:translation")
        # Formas comuns usadas por traduções brasileiras/portuguesas.
        normalized_name = re.sub(r"[\[\](){}]", " ", game_name.casefold())
        if re.search(r"(?:pt[-_ ]?br|br[-_ ]?pt|t[-_ ]?pt[-_ ]?br|translated[-_ ]?pt[-_ ]?br|trad[-_ ]?pt[-_ ]?br|brasil|brazil)", normalized_name, re.I):
            tags.append("variant:translation")
            tags.append("translation:pt-br")
            languages.append("Pt")
            regions.append("Brazil")
        extension = Path(rom_name).suffix.casefold().lstrip(".")
        if extension:
            tags.append(f"extension:{extension}")
        tags.extend(f"region:{r}" for r in dict.fromkeys(regions))
        tags.extend(f"language:{l}" for l in dict.fromkeys(languages))
        base = re.sub(r"^\[BIOS\]\s*", "", game_name, flags=re.I)
        base = re.sub(r"\s+\([^()]*\)", "", base)
        base = re.sub(r"\s+\[[^\]]*\]", "", base)
        base = re.sub(r"\s+", " ", base).strip()
        return {"base_name": base, "regions": tuple(dict.fromkeys(regions)), "languages": tuple(dict.fromkeys(languages)), "tags": tuple(dict.fromkeys(tags))}

    @classmethod
    def _name_metadata(cls, name):
        return cls._parse_name(name, name, None)

    @classmethod
    def _parse_game_roms(cls, game):
        game_name = str(game.attrib.get("name") or "").strip()
        cloneof = str(game.attrib.get("cloneof") or "").strip() or None
        if not game_name:
            return []
        release_regions = tuple(str(r.attrib.get("region") or "").strip() for r in game.findall("release") if r.attrib.get("region"))
        meta = cls._parse_name(game_name, "", cloneof, release_regions=release_regions)
        result = []
        for rom in game.findall("rom"):
            rom_name = str(rom.attrib.get("name") or "").strip()
            if not rom_name:
                continue
            try:
                size = int(rom.attrib.get("size") or 0)
            except ValueError:
                size = 0
            rom_status = str(rom.attrib.get("status") or "").strip()
            fmt = str(rom.attrib.get("format") or "").strip()
            rom_meta = cls._parse_name(game_name, rom_name, cloneof, rom_status, fmt, release_regions)
            tags = tuple(dict.fromkeys((*meta["tags"], *rom_meta["tags"])))
            result.append(_ExpectedRom(game_name, rom_name, size, str(rom.attrib.get("crc") or "").casefold(), str(rom.attrib.get("md5") or "").casefold(), str(rom.attrib.get("sha1") or "").casefold(), rom_status.casefold(), fmt, cloneof, meta["base_name"], rom_meta["regions"], rom_meta["languages"], tags))
        return result

    @classmethod
    def _load_dat(cls, path):
        try:
            root = ElementTree.parse(path).getroot()
        except (OSError, ElementTree.ParseError) as exc:
            raise NoIntroScanError(f"DAT No-Intro inválido: {path}: {exc}") from exc
        node = root.find("header")
        header = {c.tag: (c.text or "").strip() for c in node} if node is not None else {}
        return [item for game in root.findall(".//game") for item in cls._parse_game_roms(game)], header

    @staticmethod
    def _group_by_game(items):
        grouped = {}
        for item in items:
            grouped.setdefault(item.game_name, []).append(item)
        return grouped

    @staticmethod
    def _item_key(item):
        return (item.game_name.casefold(), item.rom_name.casefold(), item.size, item.sha1.casefold())

    @staticmethod
    def _evidence(item, status, **kwargs):
        return ScanEvidence(machine_name=item.game_name, rom_name=item.rom_name, status=status, expected_size=item.size, expected_crc=item.crc, expected_md5=item.md5, expected_sha1=item.sha1, merge_name=item.base_name, cloneof=item.cloneof, categories=item.tags, message=kwargs.pop("message", ""), **kwargs)

    @classmethod
    def _hash_zip_member_full(cls, zf, info):
        crc = 0
        size = 0
        md5 = hashlib.md5(usedforsecurity=False)
        sha1 = hashlib.sha1(usedforsecurity=False)
        with zf.open(info, "r") as handle:
            for chunk in iter(lambda: handle.read(cls.CHUNK_SIZE), b""):
                size += len(chunk)
                crc = zlib.crc32(chunk, crc)
                md5.update(chunk)
                sha1.update(chunk)
        return size, f"{crc & 0xFFFFFFFF:08x}", md5.hexdigest(), sha1.hexdigest()

    @classmethod
    def _hash_file(cls, path):
        with path.open("rb") as handle:
            crc = 0
            size = 0
            md5 = hashlib.md5(usedforsecurity=False)
            sha1 = hashlib.sha1(usedforsecurity=False)
            for chunk in iter(lambda: handle.read(cls.CHUNK_SIZE), b""):
                size += len(chunk)
                crc = zlib.crc32(chunk, crc)
                md5.update(chunk)
                sha1.update(chunk)
        return size, f"{crc & 0xFFFFFFFF:08x}", md5.hexdigest(), sha1.hexdigest()

    @staticmethod
    def _sha256(path):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _catalog_label(path, header):
        match = re.search(r"(\d{8}-\d{6}|\d{8})", path.name)
        return match.group(1) if match else (header.get("date") or header.get("version") or path.stem)

    @staticmethod
    def _normalize_name(value):
        value = re.sub(r"\.[A-Za-z0-9]{1,8}$", "", str(value))
        value = re.sub(r"\[[^]]+\]", " ", value)
        value = re.sub(r"\([^)]*\)", " ", value)
        value = re.sub(r"(?:translation|translated|trad(?:uced|ucao|ução)?|hack|romhack|t\+[^ ]+|h\+[^ ]+)", " ", value, flags=re.I)
        return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

    @staticmethod
    def _make_scan_id(profile):
        return f"scan_{time.strftime('%Y%m%d_%H%M%S')}_{abs(hash((profile.profile_id, time.time_ns()))) % 100000:05d}"

    @staticmethod
    def _write_jsonl(stream, record):
        stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    @classmethod
    def _emit(cls, evidence, result, stream):
        result.status_counts[evidence.status] += 1
        result.evidence.append(evidence)
        cls._write_jsonl(stream, {"record_type": "evidence", **cls._serialize(evidence)})

    @staticmethod
    def _serialize(evidence):
        return {"machine_name": evidence.machine_name, "rom_name": evidence.rom_name, "status": evidence.status, "expected_size": evidence.expected_size, "actual_size": evidence.actual_size, "expected_crc": evidence.expected_crc, "actual_crc": evidence.actual_crc, "expected_sha1": evidence.expected_sha1, "actual_sha1": evidence.actual_sha1, "expected_md5": evidence.expected_md5, "actual_md5": evidence.actual_md5, "path": evidence.path, "archive_path": evidence.archive_path, "archive_member": evidence.archive_member, "merge_name": evidence.merge_name, "optional": evidence.optional, "message": evidence.message, "error": evidence.error, "categories": list(evidence.categories), "cloneof": evidence.cloneof}

    @staticmethod
    def _log_error(result, stream, path, exc):
        result.errors += 1
        result.status_counts["ERROR"] += 1
        NoIntroScanService._write_jsonl(stream, {"record_type": "error", "path": str(path), "error": f"{type(exc).__name__}: {exc}"})


__all__ = ["NoIntroScanError", "NoIntroScanService"]
