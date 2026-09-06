"""Planejamento e execução da fase 3 do pipeline SERM.

A reconstrução consome exclusivamente um arquivo SERM-FILTER-V1. Nenhum DAT,
catálogo ou novo scan é consultado. Evidências arquivadas são reconstruídas em
arquivos ZIP quando possível; arquivos soltos e imagens como CHD são copiados.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from collections import OrderedDict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable

from .reconstruction_archive_service import ReconstructionArchiveError, ReconstructionArchiveService


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
    """Converte um filtered snapshot em um conjunto físico no destino."""

    FILTER_FORMAT = "SERM-FILTER-V1"

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
        grouped: OrderedDict[str, list[dict]] = OrderedDict()
        loose: list[dict] = []
        for evidence in payload["evidence"]:
            archive = str(evidence.get("archive_path") or "").strip()
            path = str(evidence.get("path") or "").strip()
            member = str(evidence.get("archive_member") or "").strip() or None
            source = archive or path
            if not source:
                continue
            if archive and member:
                grouped.setdefault(source, []).append(evidence)
            else:
                loose.append(evidence)

        items: list[ReconstructionItem] = []
        archive_count = 0
        chd_count = 0
        for source, entries in grouped.items():
            src = Path(source)
            output = dest / src.name
            archive_count += 1
            for entry in entries:
                member = str(entry.get("archive_member") or "").replace("\\", "/")
                items.append(ReconstructionItem(str(src), member, str(output), "archive"))

        loose_count = 0
        used_outputs: set[str] = set()
        for entry in loose:
            src = Path(str(entry.get("path") or "")).expanduser()
            if not src:
                continue
            name = src.name
            output = dest / name
            # Duplicate physical entries are represented in the scan but only
            # one copy is necessary in a reconstructed set.
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

        return ReconstructionPlan(
            filter_run_id=str(payload.get("filter_run_id") or ""),
            scan_id=str(payload.get("scan_id") or ""),
            source_filter_file=str(Path(filter_path).expanduser().resolve()),
            destination=str(dest),
            source=str(payload.get("source") or ""),
            system=str(payload.get("system") or ""),
            catalog_label=str(payload.get("catalog_label") or ""),
            scan_type=str(payload.get("scan_type") or "full"),
            item_count=len(items),
            archive_count=archive_count,
            loose_count=loose_count,
            chd_count=chd_count,
            items=tuple(items),
        )

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

        archive_groups: OrderedDict[tuple[str, str], list[str]] = OrderedDict()
        loose_items: list[ReconstructionItem] = []
        for item in plan.items:
            if item.kind == "archive":
                archive_groups.setdefault((item.source_path, item.output_path), []).append(item.archive_member or "")
            else:
                loose_items.append(item)

        total = len(archive_groups) + len(loose_items)
        done = 0
        created: list[str] = []
        errors: list[str] = []

        for (source_text, output_text), members in archive_groups.items():
            if cancel_callback and cancel_callback():
                raise ReconstructionError("Reconstrução cancelada pelo usuário.")
            source = Path(source_text)
            output = Path(output_text)
            try:
                cls._rebuild_archive(source, output, members)
                created.append(str(output))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{source}: {type(exc).__name__}: {exc}")
            done += 1
            if progress_callback:
                progress_callback(done, total)

        for item in loose_items:
            if cancel_callback and cancel_callback():
                raise ReconstructionError("Reconstrução cancelada pelo usuário.")
            source = Path(item.source_path)
            output = Path(item.output_path)
            try:
                if not source.is_file():
                    raise FileNotFoundError(source)
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, output)
                created.append(str(output))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{source}: {type(exc).__name__}: {exc}")
            done += 1
            if progress_callback:
                progress_callback(done, total)

        if errors:
            raise ReconstructionError("Reconstrução concluída com erros:\n" + "\n".join(errors[:20]))
        return {
            "destination": str(destination),
            "filter_run_id": plan.filter_run_id,
            "scan_id": plan.scan_id,
            "created_count": len(created),
            "created": created,
        }

    @staticmethod
    def _rebuild_archive(source: Path, output: Path, members: list[str]) -> None:
        if not source.is_file():
            raise FileNotFoundError(source)
        output.parent.mkdir(parents=True, exist_ok=True)
        unique_members = list(dict.fromkeys(members))
        if source.suffix.casefold() != ".zip":
            # LHA and other containers are not safely rewritten without knowing
            # their exact archive semantics. Preserve the source container.
            shutil.copy2(source, output)
            return
        temp = Path(tempfile.mkstemp(prefix="serm-rebuild-", suffix=".zip", dir=output.parent)[1])
        temp.unlink(missing_ok=True)
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


__all__ = ["ReconstructionError", "ReconstructionItem", "ReconstructionPlan", "ReconstructionService"]
