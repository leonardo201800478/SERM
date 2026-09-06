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
        set_type = cls._mame_set_type(payload)
        evidence = payload["evidence"]

        if str(payload.get("source", "")).casefold() == "mame":
            grouped, loose = cls._group_mame_evidence(evidence, set_type)
        else:
            grouped, loose = cls._group_evidence(evidence)

        items, archive_count, seen_outputs = cls._plan_archive_items(grouped, dest)
        loose_items, loose_count, chd_count = cls._plan_loose_items(loose, dest, seen_outputs)
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
        """Agrupa evidências MAME de acordo com Split/Non-Merged/Full-Merged.

        Split mantém cada máquina em seu próprio arquivo. Non-Merged torna cada
        clone autossuficiente, incorporando os membros do parent. Full-Merged
        concentra parent e clones no ZIP do parent. BIOS/devices seguem seu
        próprio set quando aparecem no snapshot.
        """
        archives: OrderedDict[str, list[dict]] = OrderedDict()
        loose: list[dict] = []
        machine_entries: dict[str, list[dict]] = {}
        machine_parent: dict[str, str] = {}

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

        for machine, entries in machine_entries.items():
            if set_type == "split":
                target_machine = machine
            elif set_type == "full_merged":
                target_machine = root_parent(machine)
            else:  # non_merged
                target_machine = machine

            for entry in entries:
                source = str(entry.get("archive_path") or "").strip()
                if set_type == "non_merged":
                    # Cada clone recebe também os membros de seus parents.
                    chain: list[str] = []
                    current = machine
                    while current:
                        chain.append(current)
                        parent = machine_parent.get(current)
                        if not parent or parent in chain:
                            break
                        current = parent
                    for chain_machine in reversed(chain):
                        for parent_entry in machine_entries.get(chain_machine, []):
                            parent_source = str(parent_entry.get("archive_path") or "").strip()
                            parent_member = str(parent_entry.get("archive_member") or "").strip()
                            if parent_source and parent_member:
                                archives.setdefault(str(dest_key(machine)), []).append(parent_entry)
                    continue
                archives.setdefault(str(dest_key(target_machine)), []).append(entry)

        return archives, loose

    @staticmethod
    def _group_output_key(machine: str) -> str:
        return machine or "unknown"

    @staticmethod
    def _plan_archive_items(
        grouped: OrderedDict[str, list[dict]], dest: Path
    ) -> tuple[list[ReconstructionItem], int, set[str]]:
        items: list[ReconstructionItem] = []
        seen_archive_outputs: set[str] = set()
        archive_count = 0
        for source, entries in grouped.items():
            source_path = Path(source)
            if source.startswith("__MAME_TARGET__:"):
                output_name = source.split(":", 1)[1]
                output = dest / f"{output_name}.zip"
            else:
                output = dest / source_path.name
            output_key = str(output).casefold()
            if output_key in seen_archive_outputs:
                continue
            seen_archive_outputs.add(output_key)
            archive_count += 1
            seen_members: set[str] = set()
            for entry in entries:
                member = str(entry.get("archive_member") or "").replace("\\", "/")
                if not member or member in seen_members:
                    continue
                seen_members.add(member)
                items.append(ReconstructionItem(str(entry.get("archive_path") or source), member, str(output), "archive"))
        return items, archive_count, seen_archive_outputs

    @staticmethod
    def _plan_loose_items(
        loose: list[dict], dest: Path, used_outputs: set[str]
    ) -> tuple[list[ReconstructionItem], int, int]:
        items: list[ReconstructionItem] = []
        loose_count = 0
        chd_count = 0
        for entry in loose:
            src_text = str(entry.get("path") or "").strip()
            if not src_text:
                continue
            src = Path(src_text).expanduser()
            output = dest / src.name
            key = str(output).casefold()
            if key in used_outputs:
                continue
            used_outputs.add(key)
            kind = "chd" if src.suffix.casefold() == ".chd" else "loose"
            if kind == "chd":
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
        return {"destination": str(destination), "filter_run_id": plan.filter_run_id, "scan_id": plan.scan_id, "created_count": len(created), "created": created, "set_type": plan.set_type}

    @staticmethod
    def _group_execution_items(items: tuple[ReconstructionItem, ...]) -> tuple[OrderedDict[tuple[str, str], list[str]], list[ReconstructionItem]]:
        archives: OrderedDict[tuple[str, str], list[str]] = OrderedDict()
        loose: list[ReconstructionItem] = []
        for item in items:
            if item.kind == "archive":
                archives.setdefault((item.source_path, item.output_path), []).append(item.archive_member or "")
            else:
                loose.append(item)
        # Reagrupar arquivos de múltiplas origens que apontam para o mesmo
        # output. Isso é necessário em Non-Merged/Full-Merged.
        by_output: OrderedDict[str, list[tuple[str, list[str]]]] = OrderedDict()
        for (source, output), members in archives.items():
            by_output.setdefault(output, []).append((source, members))
        normalized: OrderedDict[tuple[str, str], list[str]] = OrderedDict()
        for output, groups in by_output.items():
            for source, members in groups:
                normalized[(source, output)] = members
        return normalized, loose

    @classmethod
    def _execute_archives(cls, groups, created, errors, total, progress_callback, cancel_callback) -> int:
        done = 0
        by_output: OrderedDict[str, list[tuple[str, list[str]]]] = OrderedDict()
        for (source_text, output_text), members in groups.items():
            by_output.setdefault(output_text, []).append((source_text, members))
        for output_text, source_groups in by_output.items():
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
    def _rebuild_archive_from_sources(cls, source_groups, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        unique: OrderedDict[str, tuple[Path, str]] = OrderedDict()
        for source_text, members in source_groups:
            source = Path(source_text)
            if not source.is_file():
                raise FileNotFoundError(source)
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
    def _execute_loose_items(cls, items, created, errors, done, total, progress_callback, cancel_callback) -> None:
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
    def _report_progress(progress_callback: Callable[[int, int], None] | None, done: int, total: int) -> None:
        if progress_callback:
            progress_callback(done, total)

    @staticmethod
    def _rebuild_archive(source: Path, output: Path, members: list[str]) -> None:
        if not source.is_file():
            raise FileNotFoundError(source)
        output.parent.mkdir(parents=True, exist_ok=True)
        unique_members = list(dict.fromkeys(members))
        if source.suffix.casefold() != ".zip":
            shutil.copy2(source, output)
            return
        fd, temp_name = tempfile.mkstemp(prefix="serm-rebuild-", suffix=".zip", dir=output.parent)
        os.close(fd)
        temp = Path(temp_name)
        try:
            with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_STORED) as zout:
                names = set(zin.namelist())
                missing = [member for member in unique_members if member not in names]
                if missing:
                    raise ReconstructionError(f"Membro ausente em {source.name}: {missing[0]}")
                for member in unique_members:
                    info = zin.getinfo(member)
                    with zin.open(info, "r") as source_member, zout.open(info, "w") as target_member:
                        shutil.copyfileobj(source_member, target_member, length=1024 * 1024)
            temp.replace(output)
        finally:
            temp.unlink(missing_ok=True)
