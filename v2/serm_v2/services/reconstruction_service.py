"""Planejamento e execução da fase 3 do pipeline SERM."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ReconstructionItem:
    source_path: str
    archive_member: str | None
    output_path: str
    kind: str


@dataclass(frozen=True, slots=True)
class ReconstructionPlan:
    filter_run_id: str
    scan_id: str
    source_filter_file: str
    destination: str
    source: str
    system: str
    catalog_label: str
    scan_type: str
    set_type: str
    item_count: int
    archive_count: int
    loose_count: int
    chd_count: int
    items: tuple[ReconstructionItem, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class ReconstructionError(RuntimeError):
    """Erro controlado da reconstrução."""


class ReconstructionService:
    FILTER_FORMAT = "SERM-FILTER-V1"
    MAME_SET_TYPES = frozenset({"split", "non_merged", "full_merged"})
    MAME_TARGET_PREFIX = "__MAME_TARGET__:"

    @classmethod
    def load_filter(cls, path: str | Path) -> dict:
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise ReconstructionError(f"Arquivo filtrado não encontrado: {source}")
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReconstructionError(f"Não foi possível ler o arquivo filtrado: {exc}") from exc
        if payload.get("format") != cls.FILTER_FORMAT:
            raise ReconstructionError("O arquivo selecionado não é um SERM-FILTER-V1 válido.")
        if not isinstance(payload.get("evidence"), list):
            raise ReconstructionError("O arquivo filtrado não contém a lista de evidências.")
        return payload

    @classmethod
    def plan(cls, filter_path: str | Path, destination: str | Path) -> ReconstructionPlan:
        payload = cls.load_filter(filter_path)
        dest = Path(destination).expanduser().resolve()
        is_mame = str(payload.get("source", "")).casefold() == "mame"
        set_type = cls._mame_set_type(payload)

        if is_mame:
            grouped, loose = cls._group_mame_evidence(payload["evidence"], set_type)
        else:
            grouped, loose = cls._group_evidence(payload["evidence"])

        items, archive_count, seen_outputs = cls._plan_archive_items(grouped, dest)
        loose_items, loose_count, chd_count = cls._plan_loose_items(
            loose, dest, seen_outputs, set_type if is_mame else "standard"
        )
        items.extend(loose_items)
        return ReconstructionPlan(
            filter_run_id=str(payload.get("filter_run_id") or ""),
            scan_id=str(payload.get("scan_id") or ""),
            source_filter_file=str(Path(filter_path).expanduser().resolve()),
            destination=str(dest),
            source=str(payload.get("source") or ""),
            system=str(payload.get("system") or ""),
            catalog_label=str(payload.get("catalog_label") or ""),
            scan_type=str(payload.get("scan_type") or "full"),
            set_type=set_type,
            item_count=len(items),
            archive_count=archive_count,
            loose_count=loose_count,
            chd_count=chd_count,
            items=tuple(items),
        )

    @classmethod
    def _mame_set_type(cls, payload: dict) -> str:
        if str(payload.get("source", "")).casefold() != "mame":
            return "standard"
        filters = payload.get("filters")
        value = filters.get("mame_set_type") if isinstance(filters, dict) else None
        value = str(value or "split").casefold()
        return value if value in cls.MAME_SET_TYPES else "split"

    @staticmethod
    def _group_evidence(evidence: list) -> tuple[OrderedDict[str, list[dict]], list[dict]]:
        grouped: OrderedDict[str, list[dict]] = OrderedDict()
        loose: list[dict] = []
        for entry in evidence:
            if not isinstance(entry, dict):
                continue
            archive = str(entry.get("archive_path") or "").strip()
            path = str(entry.get("path") or "").strip()
            member = str(entry.get("archive_member") or "").strip() or None
            source = archive or path
            if not source:
                continue
            if archive and member:
                grouped.setdefault(source, []).append(entry)
            else:
                loose.append(entry)
        return grouped, loose

    @classmethod
    def _group_mame_evidence(
        cls, evidence: list, set_type: str
    ) -> tuple[OrderedDict[str, list[dict]], list[dict]]:
        """Agrupa ROMs MAME segundo Split, Non-Merged e Full-Merged.

        CHDs permanecem fora dos ZIPs: o MAME procura esses discos no diretório
        da machine. Eles são tratados depois, preservando essa estrutura.
        """
        machine_entries: dict[str, list[dict]] = {}
        machine_parent: dict[str, str] = {}
        loose: list[dict] = []

        for entry in evidence:
            if not isinstance(entry, dict):
                continue
            archive = str(entry.get("archive_path") or "").strip()
            member = str(entry.get("archive_member") or "").strip()
            path = str(entry.get("path") or "").strip()
            machine = str(entry.get("machine_name") or "").strip()

            if archive and member:
                machine_entries.setdefault(machine, []).append(entry)
                cloneof = str(entry.get("cloneof") or "").strip()
                if machine and cloneof:
                    machine_parent[machine] = cloneof
            elif path:
                loose.append(entry)

        def root_parent(machine: str) -> str:
            seen: set[str] = set()
            current = machine
            while current in machine_parent and current not in seen:
                seen.add(current)
                current = machine_parent[current]
            return current

        def chain_to_parent(machine: str) -> list[str]:
            chain: list[str] = []
            current = machine
            while current and current not in chain:
                chain.append(current)
                current = machine_parent.get(current, "")
            return list(reversed(chain))

        grouped: OrderedDict[str, list[dict]] = OrderedDict()
        for machine, entries in machine_entries.items():
            if not machine:
                for entry in entries:
                    grouped.setdefault(str(entry.get("archive_path")), []).append(entry)
                continue

            if set_type == "split":
                target = machine
                grouped.setdefault(cls.MAME_TARGET_PREFIX + target, []).extend(entries)
            elif set_type == "full_merged":
                target = root_parent(machine)
                grouped.setdefault(cls.MAME_TARGET_PREFIX + target, []).extend(entries)
            else:
                target = machine
                output_entries = grouped.setdefault(cls.MAME_TARGET_PREFIX + target, [])
                for chain_machine in chain_to_parent(machine):
                    output_entries.extend(machine_entries.get(chain_machine, []))

        return grouped, loose

    @classmethod
    def _plan_archive_items(
        cls, grouped: OrderedDict[str, list[dict]], dest: Path
    ) -> tuple[list[ReconstructionItem], int, set[str]]:
        items: list[ReconstructionItem] = []
        seen_outputs: set[str] = set()
        archive_count = 0
        for source, entries in grouped.items():
            if source.startswith(cls.MAME_TARGET_PREFIX):
                output = dest / f"{source.removeprefix(cls.MAME_TARGET_PREFIX)}.zip"
            else:
                output = dest / Path(source).name
            output_key = str(output).casefold()
            if output_key not in seen_outputs:
                seen_outputs.add(output_key)
                archive_count += 1
            seen_members: set[tuple[str, str]] = set()
            for entry in entries:
                archive_source = str(entry.get("archive_path") or source).strip()
                member = str(entry.get("archive_member") or "").replace("\\", "/").strip()
                if not archive_source or not member:
                    continue
                identity = (archive_source.casefold(), member.casefold())
                if identity in seen_members:
                    continue
                seen_members.add(identity)
                items.append(ReconstructionItem(archive_source, member, str(output), "archive"))
        return items, archive_count, seen_outputs

    @staticmethod
    def _plan_loose_items(
        loose: list[dict],
        dest: Path,
        used_outputs: set[str],
        set_type: str,
    ) -> tuple[list[ReconstructionItem], int, int]:
        """Planeja CHDs mantendo o layout <machine>\\<disk>.chd do MAME."""
        items: list[ReconstructionItem] = []
        loose_count = 0
        chd_count = 0
        for entry in loose:
            src_text = str(entry.get("path") or "").strip()
            if not src_text:
                continue
            src = Path(src_text).expanduser()
            is_chd = src.suffix.casefold() == ".chd"
            machine = str(entry.get("machine_name") or "").strip()

            if is_chd and machine and set_type in {"split", "non_merged", "full_merged"}:
                # Para Full-Merged, o CHD continua associado à machine de origem.
                # Para Split/Non-Merged, a machine também é o diretório do set.
                output = dest / machine / src.name
            else:
                output = dest / src.name

            key = str(output).casefold()
            if key in used_outputs:
                continue
            used_outputs.add(key)
            kind = "chd" if is_chd else "loose"
            if is_chd:
                chd_count += 1
            else:
                loose_count += 1
            items.append(ReconstructionItem(str(src), None, str(output), kind))
        return items, loose_count, chd_count

    @classmethod
    def execute(
        cls,
        plan: ReconstructionPlan,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
    ) -> dict:
        destination = Path(plan.destination)
        destination.mkdir(parents=True, exist_ok=True)
        if not plan.items:
            raise ReconstructionError("O plano não contém arquivos físicos para reconstruir.")
        archive_groups, loose_items = cls._group_execution_items(plan.items)
        total = len(archive_groups) + len(loose_items)
        created: list[str] = []
        errors: list[str] = []
        done = cls._execute_archives(archive_groups, created, errors, total, progress_callback, cancel_callback)
        cls._execute_loose_items(loose_items, created, errors, done, total, progress_callback, cancel_callback)
        if errors:
            raise ReconstructionError("Reconstrução concluída com erros:\n" + "\n".join(errors[:20]))
        return {
            "destination": str(destination),
            "filter_run_id": plan.filter_run_id,
            "scan_id": plan.scan_id,
            "created_count": len(created),
            "created": created,
            "set_type": plan.set_type,
        }

    @staticmethod
    def _group_execution_items(
        items: tuple[ReconstructionItem, ...],
    ) -> tuple[OrderedDict[str, list[tuple[str, list[str]]]], list[ReconstructionItem]]:
        archives: OrderedDict[str, list[tuple[str, list[str]]]] = OrderedDict()
        loose: list[ReconstructionItem] = []
        by_key: dict[tuple[str, str], list[str]] = {}
        for item in items:
            if item.kind == "archive":
                key = (item.output_path, item.source_path)
                by_key.setdefault(key, []).append(item.archive_member or "")
            else:
                loose.append(item)
        for (output, source), members in by_key.items():
            archives.setdefault(output, []).append((source, members))
        return archives, loose

    @classmethod
    def _execute_archives(
        cls, groups, created, errors, total, progress_callback, cancel_callback
    ) -> int:
        done = 0
        for output_text, source_groups in groups.items():
            cls._raise_if_cancelled(cancel_callback)
            try:
                cls._rebuild_archive_from_sources(source_groups, Path(output_text))
                created.append(output_text)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{output_text}: {type(exc).__name__}: {exc}")
            done += 1
            cls._report_progress(progress_callback, done, total)
        return done

    @classmethod
    def _rebuild_archive_from_sources(
        cls, source_groups: list[tuple[str, list[str]]], output: Path
    ) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        unique: OrderedDict[str, tuple[Path, str]] = OrderedDict()
        for source_text, members in source_groups:
            source = Path(source_text)
            if not source.is_file():
                raise FileNotFoundError(source)
            if source.suffix.casefold() != ".zip":
                raise ReconstructionError(f"Fonte não ZIP para reconstrução de arquivo: {source}")
            with zipfile.ZipFile(source, "r") as zin:
                names = set(zin.namelist())
                for member in dict.fromkeys(members):
                    if member not in names:
                        raise ReconstructionError(f"Membro ausente em {source.name}: {member}")
                    unique.setdefault(member, (source, member))

        fd, temp_name = tempfile.mkstemp(prefix="serm-rebuild-", suffix=".zip", dir=output.parent)
        os.close(fd)
        temp = Path(temp_name)
        try:
            with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_STORED) as zout:
                for member, (source, name) in unique.items():
                    with zipfile.ZipFile(source, "r") as zin:
                        info = zin.getinfo(name)
                        with zin.open(info, "r") as source_member, zout.open(info, "w") as target_member:
                            shutil.copyfileobj(source_member, target_member, length=1024 * 1024)
            temp.replace(output)
        finally:
            temp.unlink(missing_ok=True)

    @classmethod
    def _execute_loose_items(
        cls, items, created, errors, done, total, progress_callback, cancel_callback
    ) -> None:
        for item in items:
            cls._raise_if_cancelled(cancel_callback)
            try:
                source = Path(item.source_path)
                output = Path(item.output_path)
                if not source.is_file():
                    raise FileNotFoundError(source)
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, output)
                created.append(str(output))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{item.source_path}: {type(exc).__name__}: {exc}")
            done += 1
            cls._report_progress(progress_callback, done, total)

    @staticmethod
    def _raise_if_cancelled(cancel_callback: Callable[[], bool] | None) -> None:
        if cancel_callback and cancel_callback():
            raise ReconstructionError("Reconstrução cancelada pelo usuário.")

    @staticmethod
    def _report_progress(
        progress_callback: Callable[[int, int], None] | None, done: int, total: int
    ) -> None:
        if progress_callback:
            progress_callback(done, total)


__all__ = [
    "ReconstructionError",
    "ReconstructionItem",
    "ReconstructionPlan",
    "ReconstructionService",
]
