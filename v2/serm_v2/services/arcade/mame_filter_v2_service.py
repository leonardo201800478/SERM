"""Serviço de filtragem MAME V2 do Arcade Studio.

A unidade de filtragem é exclusivamente a machine MAME. Evidências de ROM,
CHD ou membros de arquivo servem apenas para compor a saída física depois que
as machines já foram selecionadas.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

from ...models.arcade import ArcadeGame, ArcadePlatform, PlayabilityStatus
from ...models.arcade_classification import (
    ArcadeContentType,
    ArcadeGenre,
    ArcadeHardwareFamily,
    ArcadeInputType,
    WheelAngleClass,
)
from ...runtime.paths import scans_root
from ..arcade.filter_engine import ArcadeFilterEngine, FilterRules
from ..mame_category_filter_service import MameCategoryFilterService
from ..scan_file_repository import ScanFileRepository


class MameFilterV2Service:
    """Classifica e filtra machines MAME sem contabilizar componentes."""

    _CONTENT = {
        "mechanical": {
            ArcadeContentType.MECHANICAL,
            ArcadeContentType.ELECTROMECHANICAL,
        },
        "console": {ArcadeContentType.CONSOLE},
        "handheld": {ArcadeContentType.HANDHELD},
        "fruit_machines": {
            ArcadeContentType.FRUIT_MACHINE,
            ArcadeContentType.GAMBLING,
            ArcadeContentType.CASINO,
            ArcadeContentType.REDEMPTION,
            ArcadeContentType.MEDAL,
        },
        "quiz": {ArcadeContentType.QUIZ},
        "tabletop": {ArcadeContentType.TABLETOP},
    }

    @classmethod
    def _payload(cls, path: Path) -> dict:
        payload = ScanFileRepository.load(path)
        if str(payload.get("source", "")).casefold() != "mame":
            raise ValueError("O snapshot selecionado não é um scan MAME.")
        return payload

    @classmethod
    def _games(cls, payload: dict) -> list[ArcadeGame]:
        """Converte o snapshot em uma machine única por machine_name.

        Um snapshot possui várias evidências por machine (ROMs, CHDs etc.).
        O motor recebe uma única ArcadeGame por machine para que todas as
        contagens e decisões do filtro sejam contagens de machines.
        """
        machines: dict[str, ArcadeGame] = {}
        for item in payload.get("evidence", []):
            name = str(
                item.get("machine_name")
                or item.get("machine")
                or item.get("name")
                or ""
            ).strip()
            if not name or name in machines:
                continue

            categories = list(item.get("categories") or ())
            metadata = dict(item)
            metadata["categories"] = categories
            machines[name] = ArcadeGame(
                machine_name=name,
                display_name=str(
                    item.get("description")
                    or item.get("display_name")
                    or name
                ),
                platform=ArcadePlatform.MAME,
                parent_name=str(item.get("cloneof")) if item.get("cloneof") else None,
                category=categories[0] if categories else None,
                subcategory=categories[1] if len(categories) > 1 else None,
                metadata=metadata,
            )
        return list(machines.values())

    @classmethod
    def facets(cls, path: Path) -> dict[str, list[dict[str, object]]]:
        payload = cls._payload(path)
        classifier = ArcadeFilterEngine()._classifier
        counters = {
            key: Counter()
            for key in (
                "content",
                "playability",
                "genre",
                "hardware",
                "manufacturer",
                "series",
                "input",
                "wheel",
            )
        }

        for game in cls._games(payload):
            classification = classifier.classify(game)
            counters["content"][classification.content_type.value] += 1
            counters["playability"][game.playability.value] += 1
            for value in classification.genres:
                counters["genre"][value.value] += 1
            for value in classification.hardware:
                counters["hardware"][value.value] += 1
            if classification.manufacturer:
                counters["manufacturer"][classification.manufacturer] += 1
            if classification.series:
                counters["series"][classification.series] += 1
            for value in classification.inputs:
                counters["input"][value.value] += 1
            if classification.wheel_angle is not WheelAngleClass.UNKNOWN:
                counters["wheel"][classification.wheel_angle.value] += 1

        return {
            key: [
                {"value": str(value), "count": count}
                for value, count in sorted(
                    counter.items(),
                    key=lambda pair: (-pair[1], str(pair[0]).casefold()),
                )
            ]
            for key, counter in counters.items()
        }

    @classmethod
    def _rules(cls, state) -> FilterRules:
        excluded_content = set()
        for key, types in cls._CONTENT.items():
            # Fundamental controls are explicit exclusions. False means
            # "do not exclude this class", never "exclude by default".
            if bool(state.fundamental.get(key, False)):
                excluded_content.update(types)

        excluded_names = set()
        if state.categories or state.subcategories:
            database_path = getattr(state, "database_path", None)
            if database_path:
                excluded_names = MameCategoryFilterService.matching_machine_names(
                    {
                        "categories": state.categories,
                        "subcategories": state.subcategories,
                    },
                    database_path,
                )

        excluded_genres = (
            {ArcadeGenre.DANCE}
            if bool(state.fundamental.get("dance", False))
            else set()
        )

        def enum(values, enum_type):
            allowed = {member.value for member in enum_type}
            return {
                enum_type(value)
                for value in values
                if value in allowed
            }

        return FilterRules(
            excluded_machine_names=frozenset(excluded_names),
            excluded_content_types=frozenset(excluded_content),
            excluded_genres=frozenset(excluded_genres),
            included_content_types=frozenset(
                enum(state.content, ArcadeContentType)
            ),
            included_playability=frozenset(
                enum(state.playability, PlayabilityStatus)
            ),
            included_genres=frozenset(enum(state.genre, ArcadeGenre)),
            included_hardware=frozenset(
                enum(state.hardware, ArcadeHardwareFamily)
            ),
            included_manufacturers=frozenset(state.manufacturer),
            included_series=frozenset(state.series),
            included_inputs=frozenset(enum(state.input, ArcadeInputType)),
            included_wheel_angles=frozenset(
                enum(state.wheel, WheelAngleClass)
            ),
            include_bios=state.mame_include_bios,
            include_devices=state.mame_include_devices,
            include_optional=state.mame_include_optional,
            working_only=state.mame_working_only,
            parents_only=state.mame_clone_policy == "parents_only",
        )

    @classmethod
    def preview(cls, path: Path, state) -> dict:
        payload = cls._payload(path)
        games = cls._games(payload)
        result = ArcadeFilterEngine().apply(games, cls._rules(state))
        reasons = Counter(
            item.trace.rule or item.trace.stage.value
            for item in result.excluded
        )
        return {
            "unit": "machines",
            "input_count": result.total_input,
            "output_count": result.included_count,
            "filtered_count": result.excluded_count,
            "filter_counts": dict(reasons),
            "stage_counts": {
                stage.value: count
                for stage, count in result.counts_after_stage.items()
            },
        }

    @classmethod
    def apply(cls, path: Path, state) -> dict:
        payload = cls._payload(path)
        games = cls._games(payload)
        result = ArcadeFilterEngine().apply(games, cls._rules(state))
        kept_names = {item.game.machine_name for item in result.games}

        # Physical evidence is preserved only for the machines selected by
        # the machine-level engine. This does not alter any machine counts.
        evidence = list(payload.get("evidence", []))
        kept_evidence = [
            item
            for item in evidence
            if str(
                item.get("machine_name")
                or item.get("machine")
                or item.get("name")
                or ""
            ) in kept_names
        ]
        reasons = Counter(
            item.trace.rule or item.trace.stage.value
            for item in result.excluded
        )
        run_id = uuid4().hex[:16]
        out_dir = scans_root() / "filtered" / "mame"
        out_dir.mkdir(parents=True, exist_ok=True)
        label = re.sub(
            r"[^A-Za-z0-9._-]+",
            "_",
            str(payload.get("catalog_label") or "catalog"),
        )
        output_path = (
            out_dir
            / f"MAME_{label}_{payload.get('scan_type', 'arcade')}_FILTER_{run_id}.json"
        )
        output = {
            "format": "SERM-FILTER-V2",
            "schema_version": 2,
            "filter_run_id": run_id,
            "scan_id": payload.get("scan_id"),
            "profile_id": state.profile_id,
            "source": "mame",
            "system": payload.get("system"),
            "scan_type": payload.get("scan_type", "arcade"),
            "catalog_label": payload.get("catalog_label"),
            "catalog_hash": payload.get("catalog_hash"),
            "source_scan_file": str(path.resolve()),
            "created_at": time.time(),
            "unit": "machines",
            "input_count": result.total_input,
            "output_count": result.included_count,
            "filtered_count": result.excluded_count,
            "physical_evidence_count": len(kept_evidence),
            "filter_counts": dict(reasons),
            "stage_counts": {
                stage.value: count
                for stage, count in result.counts_after_stage.items()
            },
            "filters": {
                "fundamental": dict(state.fundamental),
                "set_type": state.mame_set_type,
                "clone_policy": state.mame_clone_policy,
                "include_bios": state.mame_include_bios,
                "include_devices": state.mame_include_devices,
                "include_chd": state.mame_include_chd,
                "include_optional": state.mame_include_optional,
                "working_only": state.mame_working_only,
                "categories": list(state.categories),
                "subcategories": list(state.subcategories),
                "content": list(state.content),
                "playability": list(state.playability),
                "genre": list(state.genre),
                "hardware": list(state.hardware),
                "manufacturer": list(state.manufacturer),
                "series": list(state.series),
                "input": list(state.input),
                "wheel": list(state.wheel),
            },
            "machines": sorted(kept_names),
            "evidence": kept_evidence,
            "output_file": str(output_path),
        }
        output_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        output["filtered_file_path"] = str(output_path)
        return output


__all__ = ["MameFilterV2Service"]
