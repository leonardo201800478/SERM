"""Aplicação rápida de filtros sobre um snapshot de scan já concluído."""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

from ..runtime.paths import scans_root
from .mame_fundamental_filter_service import CATEGORY_PATTERNS, DEFAULT_FILTERS
from .scan_file_repository import ScanFileRepository


class ScanFilterService:
    """Nunca toca no scan bruto; produz somente um resultado filtrado novo."""

    @staticmethod
    def _matches(categories: list[str] | tuple[str, ...], patterns: tuple[str, ...]) -> bool:
        values = [str(value).casefold() for value in categories]
        return any(pattern.casefold() in value for value in values for pattern in patterns)

    @classmethod
    def apply_mame_fundamental(cls, scan_path: Path, values: dict[str, bool], *, profile_id: str) -> dict:
        payload = ScanFileRepository.load(scan_path)
        if str(payload.get("source", "")).casefold() != "mame":
            raise ValueError("Os filtros fundamentais são exclusivos do MAME.")

        evidence = list(payload.get("evidence", []))
        enabled = {key for key, default in DEFAULT_FILTERS.items() if bool(values.get(key, default))}
        kept: list[dict] = []
        filtered: list[dict] = []
        reasons = Counter()
        for item in evidence:
            categories = tuple(item.get("categories") or ())
            reason = None
            for key in enabled:
                if cls._matches(categories, CATEGORY_PATTERNS[key]):
                    reason = key
                    break
            if reason:
                filtered.append({**item, "filter_reason": reason})
                reasons[reason] += 1
            else:
                kept.append(item)

        run_id = uuid4().hex[:16]
        out_dir = scans_root() / "filtered" / "mame"
        out_dir.mkdir(parents=True, exist_ok=True)
        label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(payload.get("catalog_label", "catalog")))
        out_path = out_dir / f"MAME_{label}_{payload.get('scan_type', 'arcade')}_FILTER_{run_id}.json"
        result = {
            "format": "SERM-FILTER-V1",
            "filter_run_id": run_id,
            "scan_id": payload.get("scan_id"),
            "profile_id": profile_id,
            "source": payload.get("source"),
            "system": payload.get("system"),
            "scan_type": payload.get("scan_type"),
            "catalog_label": payload.get("catalog_label"),
            "catalog_hash": payload.get("catalog_hash"),
            "source_scan_file": str(scan_path),
            "created_at": time.time(),
            "input_count": len(evidence),
            "output_count": len(kept),
            "filtered_count": len(filtered),
            "filter_counts": dict(reasons),
            "filters": {key: bool(values.get(key, default)) for key, default in DEFAULT_FILTERS.items()},
            "evidence": kept,
        }
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        result["filtered_file_path"] = str(out_path)
        return result


__all__ = ["ScanFilterService"]
