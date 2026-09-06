"""Aplicação rápida de filtros sobre um snapshot de scan já concluído."""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

from ..runtime.paths import database_path, scans_root
from .mame_category_filter_service import MameCategoryFilterService
from .mame_fundamental_filter_service import CATEGORY_PATTERNS, DEFAULT_FILTERS
from .scan_file_repository import ScanFileRepository


class ScanFilterService:
    """Nunca toca no scan bruto; produz somente um resultado filtrado novo."""

    VALID_STATUSES = frozenset({"CURRENT", "DUPLICATE"})

    @staticmethod
    def _matches(categories: list[str] | tuple[str, ...], patterns: tuple[str, ...]) -> bool:
        values = [str(value).casefold() for value in categories]
        return any(pattern.casefold() in value for value in values for pattern in patterns)

    @classmethod
    def apply_mame(
        cls,
        scan_path: Path,
        profile,
        fundamental_values: dict[str, bool],
        category_values: dict[str, list[str]] | None = None,
    ) -> dict:
        payload = ScanFileRepository.load(scan_path)
        if str(payload.get("source", "")).casefold() != "mame":
            raise ValueError("Os filtros MAME só podem ser aplicados a um scan MAME.")
        evidence = list(payload.get("evidence", []))
        enabled = {
            key
            for key, default in DEFAULT_FILTERS.items()
            if bool(fundamental_values.get(key, default))
        }
        category_values = category_values or {"categories": [], "subcategories": []}
        category_names = MameCategoryFilterService.matching_machine_names(
            category_values, database_path()
        )
        kept: list[dict] = []
        reasons = Counter()
        for item in evidence:
            reason = cls._selection_reason(item, profile, enabled, category_names)
            if reason:
                reasons[reason] += 1
            else:
                kept.append(item)
        run_id = uuid4().hex[:16]
        out_dir = scans_root() / "filtered" / "mame"
        out_dir.mkdir(parents=True, exist_ok=True)
        label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(payload.get("catalog_label", "catalog")))
        scan_type = str(payload.get("scan_type", "arcade"))
        out_path = out_dir / f"MAME_{label}_{scan_type}_FILTER_{run_id}.json"
        result = {
            "format": "SERM-FILTER-V1",
            "filter_run_id": run_id,
            "scan_id": payload.get("scan_id"),
            "profile_id": str(profile.profile_id),
            "source": payload.get("source"),
            "system": payload.get("system"),
            "scan_type": scan_type,
            "catalog_label": payload.get("catalog_label"),
            "catalog_hash": payload.get("catalog_hash"),
            "source_scan_file": str(scan_path),
            "created_at": time.time(),
            "input_count": len(evidence),
            "output_count": len(kept),
            "filtered_count": len(evidence) - len(kept),
            "filter_counts": dict(reasons),
            "filters": {
                "fundamental": {
                    key: bool(fundamental_values.get(key, default))
                    for key, default in DEFAULT_FILTERS.items()
                },
                "catlist": {
                    "categories": sorted(category_values.get("categories", [])),
                    "subcategories": sorted(category_values.get("subcategories", [])),
                },
                "mame_clone_policy": str(getattr(profile, "mame_clone_policy", "with_clones")),
                "mame_include_bios": bool(getattr(profile, "mame_include_bios", False)),
                "mame_include_devices": bool(getattr(profile, "mame_include_devices", False)),
                "mame_include_optional": bool(getattr(profile, "mame_include_optional", True)),
                "mame_working_only": bool(getattr(profile, "mame_working_only", False)),
                "mame_set_type": str(getattr(profile, "mame_set_type", "split")),
            },
            "evidence": kept,
        }
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        result["filtered_file_path"] = str(out_path)
        return result

    @classmethod
    def preview_mame(
        cls,
        scan_path: Path,
        profile,
        fundamental_values: dict[str, bool],
        category_values: dict[str, list[str]] | None = None,
    ) -> dict:
        payload = ScanFileRepository.load(scan_path)
        evidence = list(payload.get("evidence", []))
        category_values = category_values or {"categories": [], "subcategories": []}
        category_names = MameCategoryFilterService.matching_machine_names(
            category_values, database_path()
        )
        enabled = {
            key
            for key, default in DEFAULT_FILTERS.items()
            if bool(fundamental_values.get(key, default))
        }
        reasons = Counter()
        kept = 0
        for item in evidence:
            reason = cls._selection_reason(item, profile, enabled, category_names)
            if reason:
                reasons[reason] += 1
            else:
                kept += 1
        return {
            "catalog_label": payload.get("catalog_label"),
            "scan_type": payload.get("scan_type"),
            "input_count": len(evidence),
            "output_count": kept,
            "filtered_count": len(evidence) - kept,
            "filter_counts": dict(reasons),
            "status_counts": dict(payload.get("status_counts") or {}),
        }

    @classmethod
    def _selection_reason(
        cls, item: dict, profile, enabled: set[str], category_names: set[str]
    ) -> str | None:
        status = str(item.get("status") or "").upper()
        if status not in cls.VALID_STATUSES:
            return status.lower() or "invalid_status"
        machine_name = str(
            item.get("machine_name") or item.get("machine") or item.get("name") or ""
        )
        if machine_name in category_names:
            return "catlist"
        categories = tuple(item.get("categories") or ())
        if "mechanical" in enabled and (
            str(item.get("ismechanical") or "").casefold() in {"yes", "true", "1"}
            or cls._matches(categories, CATEGORY_PATTERNS["mechanical"])
        ):
            return "mechanical"
        for key in ("dance", "console", "handheld", "fruit_machines"):
            if key in enabled and cls._matches(categories, CATEGORY_PATTERNS[key]):
                return key
        if (
            not bool(getattr(profile, "mame_include_bios", False))
            and str(item.get("isbios") or "").casefold() == "yes"
        ):
            return "bios"
        if (
            not bool(getattr(profile, "mame_include_devices", False))
            and str(item.get("isdevice") or "").casefold() == "yes"
        ):
            return "device"
        if not bool(getattr(profile, "mame_include_optional", True)) and str(
            item.get("optional") or ""
        ).casefold() in {"yes", "true", "1"}:
            return "optional"
        if bool(getattr(profile, "mame_working_only", False)) and str(
            item.get("runnable") or ""
        ).casefold() not in {"yes", "true", "1"}:
            return "not_working"
        if str(getattr(profile, "mame_clone_policy", "with_clones")) == "parents_only" and item.get(
            "cloneof"
        ):
            return "clone"
        return None


__all__ = ["ScanFilterService"]
