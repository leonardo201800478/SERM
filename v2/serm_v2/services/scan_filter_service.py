"""Adaptador de snapshot para o motor unificado de filtros do Arcade Studio."""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

from ..models.arcade import ArcadeGame, ArcadePlatform, PlayabilityStatus
from ..models.arcade_classification import ArcadeContentType
from ..runtime.paths import database_path, scans_root
from .arcade.filter_engine import ArcadeFilterEngine, FilterRules
from .mame_category_filter_service import MameCategoryFilterService
from .mame_fundamental_filter_service import DEFAULT_FILTERS
from .scan_file_repository import ScanFileRepository


class ScanFilterService:
    """Adapta snapshots de scan para o único motor lógico de filtros.

    Este serviço não contém mais regras de seleção. Ele apenas:
    1. lê o snapshot;
    2. converte as evidências para o domínio do Arcade Studio;
    3. traduz o perfil/UI em ``FilterRules``;
    4. executa ``ArcadeFilterEngine``;
    5. persiste o resultado.
    """

    VALID_STATUSES = frozenset({"CURRENT", "DUPLICATE"})
    _FUNDAMENTAL_CONTENT = {
        "mechanical": ArcadeContentType.MECHANICAL,
        "dance": ArcadeContentType.ARCADE,
        "console": ArcadeContentType.CONSOLE,
        "handheld": ArcadeContentType.HANDHELD,
        "fruit_machines": ArcadeContentType.FRUIT_MACHINE,
        "quiz": ArcadeContentType.QUIZ,
        "tabletop": ArcadeContentType.TABLETOP,
    }

    @classmethod
    def apply_mame(
        cls,
        scan_path: Path,
        profile,
        fundamental_values: dict[str, bool],
        category_values: dict[str, list[str]] | None = None,
    ) -> dict:
        payload = cls._load_mame(scan_path)
        evidence = list(payload.get("evidence", []))
        category_values = category_values or {"categories": [], "subcategories": []}
        games = cls._games_from_evidence(evidence)
        rules = cls._build_rules(profile, fundamental_values, category_values)
        result = ArcadeFilterEngine().apply(games, rules)

        kept_names = {item.game.machine_name for item in result.games}
        kept = [item for item in evidence if cls._machine_name(item) in kept_names]
        reasons = cls._reason_counts(result.excluded)

        run_id = uuid4().hex[:16]
        out_dir = scans_root() / "filtered" / "mame"
        out_dir.mkdir(parents=True, exist_ok=True)
        label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(payload.get("catalog_label", "catalog")))
        scan_type = str(payload.get("scan_type", "arcade"))
        out_path = out_dir / f"MAME_{label}_{scan_type}_FILTER_{run_id}.json"
        output = cls._build_result(
            payload,
            scan_path,
            profile,
            fundamental_values,
            category_values,
            kept,
            reasons,
            rules,
            run_id,
            out_path,
            result,
        )
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        output["filtered_file_path"] = str(out_path)
        return output

    @classmethod
    def preview_mame(
        cls,
        scan_path: Path,
        profile,
        fundamental_values: dict[str, bool],
        category_values: dict[str, list[str]] | None = None,
    ) -> dict:
        payload = cls._load_mame(scan_path)
        evidence = list(payload.get("evidence", []))
        category_values = category_values or {"categories": [], "subcategories": []}
        rules = cls._build_rules(profile, fundamental_values, category_values)
        result = ArcadeFilterEngine().apply(cls._games_from_evidence(evidence), rules)
        reasons = cls._reason_counts(result.excluded)
        return {
            "catalog_label": payload.get("catalog_label"),
            "scan_type": payload.get("scan_type"),
            "input_count": len(evidence),
            "output_count": result.included_count,
            "filtered_count": result.excluded_count,
            "filter_counts": dict(reasons),
            "stage_counts": {stage.value: count for stage, count in result.counts_after_stage.items()},
            "status_counts": dict(payload.get("status_counts") or {}),
        }

    @classmethod
    def _load_mame(cls, scan_path: Path) -> dict:
        payload = ScanFileRepository.load(scan_path)
        if str(payload.get("source", "")).casefold() != "mame":
            raise ValueError("Os filtros MAME só podem ser aplicados a um scan MAME.")
        return payload

    @classmethod
    def _games_from_evidence(cls, evidence: list[dict]) -> list[ArcadeGame]:
        games: list[ArcadeGame] = []
        for item in evidence:
            status = str(item.get("status") or "").upper()
            if status not in cls.VALID_STATUSES:
                continue
            machine_name = cls._machine_name(item)
            if not machine_name:
                continue
            metadata = dict(item)
            metadata["categories"] = list(item.get("categories") or ())
            metadata["playability"] = item.get("playability") or item.get("playability_status")
            games.append(
                ArcadeGame(
                    machine_name=machine_name,
                    display_name=str(item.get("description") or item.get("display_name") or machine_name),
                    platform=ArcadePlatform.MAME,
                    parent_name=str(item.get("cloneof")) if item.get("cloneof") else None,
                    category=(item.get("categories") or [None])[0] if item.get("categories") else None,
                    subcategory=(item.get("categories") or [None, None])[1] if len(item.get("categories") or ()) > 1 else None,
                    metadata=metadata,
                )
            )
        return games

    @classmethod
    def _build_rules(
        cls,
        profile,
        fundamental_values: dict[str, bool],
        category_values: dict[str, list[str]],
    ) -> FilterRules:
        excluded_content = {
            cls._FUNDAMENTAL_CONTENT[key]
            for key, default in DEFAULT_FILTERS.items()
            if key in cls._FUNDAMENTAL_CONTENT and not bool(fundamental_values.get(key, default))
        }
        excluded_names = MameCategoryFilterService.matching_machine_names(
            category_values, database_path()
        )
        included_playability = cls._playability_values(profile)
        return FilterRules(
            excluded_machine_names=frozenset(excluded_names),
            excluded_content_types=frozenset(excluded_content),
            included_playability=included_playability,
            include_bios=bool(getattr(profile, "mame_include_bios", False)),
            include_devices=bool(getattr(profile, "mame_include_devices", False)),
            include_optional=bool(getattr(profile, "mame_include_optional", True)),
            working_only=bool(getattr(profile, "mame_working_only", False)),
            parents_only=str(getattr(profile, "mame_clone_policy", "with_clones")) == "parents_only",
        )

    @staticmethod
    def _playability_values(profile) -> frozenset[PlayabilityStatus]:
        raw = getattr(profile, "mame_playability", None)
        if raw is None:
            raw = getattr(profile, "included_playability", None)
        if not raw:
            return frozenset()
        values: set[PlayabilityStatus] = set()
        for value in raw:
            try:
                values.add(value if isinstance(value, PlayabilityStatus) else PlayabilityStatus(str(value)))
            except ValueError:
                continue
        return frozenset(values)

    @staticmethod
    def _machine_name(item: dict) -> str:
        return str(item.get("machine_name") or item.get("machine") or item.get("name") or "")

    @staticmethod
    def _reason_counts(excluded) -> Counter[str]:
        return Counter(item.trace.rule or item.trace.stage.value for item in excluded)

    @staticmethod
    def _build_result(
        payload: dict,
        scan_path: Path,
        profile,
        fundamental_values: dict[str, bool],
        category_values: dict[str, list[str]],
        kept: list[dict],
        reasons: Counter[str],
        rules: FilterRules,
        run_id: str,
        out_path: Path,
        engine_result,
    ) -> dict:
        return {
            "format": "SERM-FILTER-V2",
            "schema_version": 2,
            "filter_run_id": run_id,
            "scan_id": payload.get("scan_id"),
            "profile_id": str(profile.profile_id),
            "source": payload.get("source"),
            "system": payload.get("system"),
            "scan_type": payload.get("scan_type", "arcade"),
            "catalog_label": payload.get("catalog_label"),
            "catalog_hash": payload.get("catalog_hash"),
            "source_scan_file": str(scan_path.resolve()),
            "created_at": time.time(),
            "input_count": len(payload.get("evidence", [])),
            "output_count": len(kept),
            "filtered_count": len(payload.get("evidence", [])) - len(kept),
            "filter_counts": dict(reasons),
            "stage_counts": {stage.value: count for stage, count in engine_result.counts_after_stage.items()},
            "filters": {
                "fundamental": {
                    key: bool(fundamental_values.get(key, default))
                    for key, default in DEFAULT_FILTERS.items()
                },
                "catlist": {
                    "excluded_categories": sorted(category_values.get("categories", [])),
                    "excluded_subcategories": sorted(category_values.get("subcategories", [])),
                },
                "mame_clone_policy": str(getattr(profile, "mame_clone_policy", "with_clones")),
                "mame_include_bios": rules.include_bios,
                "mame_include_devices": rules.include_devices,
                "mame_include_optional": rules.include_optional,
                "mame_working_only": rules.working_only,
                "mame_playability": sorted(value.value for value in rules.included_playability),
                "mame_set_type": str(getattr(profile, "mame_set_type", "split")),
            },
            "evidence": kept,
            "output_file": str(out_path),
        }


__all__ = ["ScanFilterService"]
