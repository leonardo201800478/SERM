"""Confronto entre ListXML MAME e um snapshot físico de scan V2."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...models.arcade import RomStatus


@dataclass(frozen=True, slots=True)
class ExpectedComponent:
    machine_name: str
    component_type: str
    name: str
    size: int | None = None
    crc: str | None = None
    sha1: str | None = None
    md5: str | None = None
    merge: str | None = None
    optional: bool = False


@dataclass(frozen=True, slots=True)
class ComponentComparison:
    expected: ExpectedComponent
    status: RomStatus
    physical_path: str | None = None
    actual_size: int | None = None
    actual_crc: str | None = None
    actual_sha1: str | None = None
    actual_md5: str | None = None
    scan_status: str | None = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class MachineComparison:
    machine_name: str
    description: str
    parent: str | None
    year: str | None
    manufacturer: str | None
    components: tuple[ComponentComparison, ...]

    @property
    def status(self) -> RomStatus:
        statuses = {item.status for item in self.components}
        if not statuses:
            return RomStatus.UNKNOWN
        for status in (RomStatus.INVALID, RomStatus.MISSING, RomStatus.INCOMPLETE,
                       RomStatus.REPAIRABLE, RomStatus.OK, RomStatus.UNKNOWN):
            if status in statuses:
                return status
        return RomStatus.UNKNOWN

    @property
    def rom_count(self) -> int:
        return sum(item.expected.component_type == "ROM" for item in self.components)

    @property
    def chd_count(self) -> int:
        return sum(item.expected.component_type == "CHD" for item in self.components)


@dataclass(frozen=True, slots=True)
class ScanComparisonResult:
    scan_path: Path
    scan_id: str | None
    catalog_label: str | None
    machines: tuple[MachineComparison, ...]
    orphan_items: int

    @property
    def machine_count(self) -> int:
        return len(self.machines)

    @property
    def component_count(self) -> int:
        return sum(len(machine.components) for machine in self.machines)

    @property
    def status_counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in RomStatus}
        for machine in self.machines:
            counts[machine.status.value] += 1
        return counts


class ArcadeScanComparisonService:
    """Compara as evidências físicas de um scan com o ListXML escolhido."""

    def load_scan(self, path: Path) -> dict[str, Any]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("O arquivo de scan deve conter um objeto JSON na raiz.")
        if payload.get("format") not in {None, "SERM-SCAN-V2"}:
            raise ValueError("Formato de scan não reconhecido pelo SERM V2.")
        if not isinstance(payload.get("evidence"), list):
            raise ValueError("O scan não contém uma lista de evidências válida.")
        return payload

    def compare(self, listxml_text: str, scan_path: Path) -> ScanComparisonResult:
        payload = self.load_scan(scan_path)
        catalog = self._parse_listxml(listxml_text)
        evidence = [item for item in payload["evidence"] if isinstance(item, dict)]
        by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for item in evidence:
            machine = str(item.get("machine_name") or "").strip()
            name = str(item.get("rom_name") or item.get("disk_name") or "").strip()
            kind = str(item.get("item_type") or "ROM").upper()
            if machine and name:
                by_key.setdefault((machine, kind, name), []).append(item)

        grouped: dict[str, list[ComponentComparison]] = {}
        for component in catalog["components"]:
            key = (component.machine_name, component.component_type, component.name)
            grouped.setdefault(component.machine_name, []).append(
                self._resolve(component, by_key.get(key, []))
            )

        expected_keys = {
            (item.machine_name, item.component_type, item.name)
            for item in catalog["components"]
        }
        orphan_items = sum(
            1 for item in evidence
            if (
                str(item.get("machine_name") or "").strip(),
                str(item.get("item_type") or "ROM").upper(),
                str(item.get("rom_name") or item.get("disk_name") or "").strip(),
            ) not in expected_keys
        )
        machines = tuple(
            MachineComparison(
                machine_name=name,
                description=catalog["metadata"].get(name, (name, None, None, None))[0],
                parent=catalog["metadata"].get(name, (name, None, None, None))[1],
                year=catalog["metadata"].get(name, (name, None, None, None))[2],
                manufacturer=catalog["metadata"].get(name, (name, None, None, None))[3],
                components=tuple(grouped[name]),
            )
            for name in sorted(grouped, key=str.casefold)
        )
        return ScanComparisonResult(
            scan_path=Path(scan_path),
            scan_id=str(payload.get("scan_id") or "") or None,
            catalog_label=str(payload.get("catalog_label") or "") or None,
            machines=machines,
            orphan_items=orphan_items,
        )

    @staticmethod
    def _parse_listxml(text: str) -> dict[str, Any]:
        root = ET.fromstring(text)
        components: list[ExpectedComponent] = []
        metadata: dict[str, tuple[str, str | None, str | None, str | None]] = {}
        for machine in root.findall("machine"):
            machine_name = str(machine.get("name") or "").strip()
            if not machine_name:
                continue
            metadata[machine_name] = (
                (machine.findtext("description") or machine_name).strip(),
                ArcadeScanComparisonService._text(machine.get("cloneof")),
                ArcadeScanComparisonService._text(machine.findtext("year")),
                ArcadeScanComparisonService._text(machine.findtext("manufacturer")),
            )
            for rom in machine.findall("rom"):
                components.append(ExpectedComponent(
                    machine_name, "ROM", str(rom.get("name") or "").strip(),
                    ArcadeScanComparisonService._int(rom.get("size")),
                    ArcadeScanComparisonService._text(rom.get("crc")),
                    ArcadeScanComparisonService._text(rom.get("sha1")),
                    ArcadeScanComparisonService._text(rom.get("md5")),
                    ArcadeScanComparisonService._text(rom.get("merge")),
                    str(rom.get("optional") or "").casefold() in {"yes", "true", "1"},
                ))
            for disk in machine.findall("disk"):
                components.append(ExpectedComponent(
                    machine_name, "CHD", str(disk.get("name") or "").strip(),
                    sha1=ArcadeScanComparisonService._text(disk.get("sha1")),
                    md5=ArcadeScanComparisonService._text(disk.get("md5")),
                    merge=ArcadeScanComparisonService._text(disk.get("merge")),
                    optional=str(disk.get("optional") or "").casefold() in {"yes", "true", "1"},
                ))
        return {"components": [item for item in components if item.name], "metadata": metadata}

    @classmethod
    def _resolve(cls, expected: ExpectedComponent, candidates: list[dict[str, Any]]) -> ComponentComparison:
        if not candidates:
            return ComponentComparison(expected, RomStatus.MISSING,
                                       message="Esperado pelo ListXML, mas não apareceu no scan.")
        if len(candidates) > 1:
            return ComponentComparison(expected, RomStatus.REPAIRABLE,
                                       scan_status="DUPLICATE",
                                       message=f"{len(candidates)} evidências físicas correspondentes.")
        item = candidates[0]
        scan_status = str(item.get("status") or "").upper()
        actual_size = cls._int(item.get("actual_size"))
        actual_crc = cls._text(item.get("actual_crc"))
        actual_sha1 = cls._text(item.get("actual_sha1"))
        actual_md5 = cls._text(item.get("actual_md5"))
        status = cls._identity_status(expected, scan_status, actual_size, actual_crc, actual_sha1, actual_md5)
        return ComponentComparison(
            expected, status,
            physical_path=cls._text(item.get("path")) or cls._text(item.get("archive_path")),
            actual_size=actual_size, actual_crc=actual_crc, actual_sha1=actual_sha1,
            actual_md5=actual_md5, scan_status=scan_status or None,
            message=str(item.get("message") or ""),
        )

    @staticmethod
    def _identity_status(expected: ExpectedComponent, scan_status: str,
                         actual_size: int | None, actual_crc: str | None,
                         actual_sha1: str | None, actual_md5: str | None) -> RomStatus:
        if expected.sha1 and actual_sha1 and expected.sha1.casefold() == actual_sha1.casefold():
            return RomStatus.OK
        if expected.md5 and actual_md5 and expected.md5.casefold() == actual_md5.casefold():
            return RomStatus.OK
        if (expected.crc and expected.size is not None and actual_crc and actual_size is not None
                and expected.crc.casefold() == actual_crc.casefold() and expected.size == actual_size):
            return RomStatus.OK
        return {
            "CURRENT": RomStatus.OK, "DUPLICATE": RomStatus.OK,
            "MISSING": RomStatus.MISSING, "WRONG": RomStatus.INVALID,
            "ERROR": RomStatus.INVALID,
        }.get(scan_status, RomStatus.UNKNOWN)

    @staticmethod
    def _text(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _int(value: object) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


__all__ = ["ArcadeScanComparisonService", "ComponentComparison", "ExpectedComponent",
           "MachineComparison", "ScanComparisonResult"]
