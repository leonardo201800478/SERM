"""Serviço de filtragem MAME V2 do Arcade Studio."""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from ...models.arcade import ArcadeGame, ArcadePlatform, PlayabilityStatus
from ...models.arcade_classification import ArcadeContentType, ArcadeGenre, ArcadeHardwareFamily, ArcadeInputType, WheelAngleClass
from ...runtime.paths import database_path, scans_root
from ..arcade.filter_engine import ArcadeFilterEngine, FilterRules
from ..mame_category_filter_service import MameCategoryFilterService
from ..scan_file_repository import ScanFileRepository


class MameFilterV2Service:
    """Classifica e filtra machines MAME sem contabilizar componentes."""

    _CONTENT = {
        "mechanical": {ArcadeContentType.MECHANICAL, ArcadeContentType.ELECTROMECHANICAL},
        "console": {ArcadeContentType.CONSOLE},
        "handheld": {ArcadeContentType.HANDHELD},
        "fruit_machines": {ArcadeContentType.FRUIT_MACHINE, ArcadeContentType.GAMBLING, ArcadeContentType.CASINO, ArcadeContentType.REDEMPTION, ArcadeContentType.MEDAL},
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
        machines: dict[str, ArcadeGame] = {}
        for item in payload.get("evidence", []):
            name = str(item.get("machine_name") or item.get("machine") or item.get("name") or "").strip()
            if not name or name in machines:
                continue
            categories = list(item.get("categories") or ())
            metadata = dict(item); metadata["categories"] = categories
            machines[name] = ArcadeGame(
                machine_name=name,
                display_name=str(item.get("description") or item.get("display_name") or name),
                platform=ArcadePlatform.MAME,
                parent_name=str(item.get("cloneof")) if item.get("cloneof") else None,
                category=categories[0] if categories else None,
                subcategory=categories[1] if len(categories) > 1 else None,
                metadata=metadata,
            )
        return list(machines.values())

    @classmethod
    def facets(cls, path: Path) -> dict[str, list[dict[str, object]]]:
        payload = cls._payload(path); classifier = ArcadeFilterEngine()._classifier
        counters = {key: Counter() for key in ("year", "content", "playability", "genre", "hardware", "manufacturer", "series", "input", "wheel")}
        for game in cls._games(payload):
            classification = classifier.classify(game)
            year = cls._year(game)
            if year is not None: counters["year"][str(year)] += 1
            counters["content"][classification.content_type.value] += 1; counters["playability"][game.playability.value] += 1
            for value in classification.genres: counters["genre"][value.value] += 1
            for value in classification.hardware: counters["hardware"][value.value] += 1
            if classification.manufacturer: counters["manufacturer"][classification.manufacturer] += 1
            if classification.series: counters["series"][classification.series] += 1
            for value in classification.inputs: counters["input"][value.value] += 1
            if classification.wheel_angle is not WheelAngleClass.UNKNOWN: counters["wheel"][classification.wheel_angle.value] += 1
        return {key: [{"value": str(value), "count": count} for value, count in sorted(counter.items(), key=lambda pair: (-pair[1], str(pair[0]).casefold()))] for key, counter in counters.items()}

    @staticmethod
    def _metadata_text(game: ArcadeGame) -> str:
        def flatten(value) -> str:
            if isinstance(value, dict): return " ".join(flatten(v) for v in value.values())
            if isinstance(value, (list, tuple, set)): return " ".join(flatten(v) for v in value)
            return str(value)
        return f"{game.machine_name} {game.display_name} {flatten(game.metadata)}".casefold()

    @staticmethod
    def _year(game: ArcadeGame) -> int | None:
        value = game.metadata.get("year")
        if value is not None:
            match = re.search(r"\d{4}", str(value)); return int(match.group()) if match else None
        match = re.search(r"(?:^|\D)((?:19|20)\d{2})(?:\D|$)", MameFilterV2Service._metadata_text(game)); return int(match.group(1)) if match else None

    @classmethod
    def _candidate_names(cls, games: list[ArcadeGame], state) -> set[str] | None:
        candidate_sets: list[set[str]] = []
        if state.categories or state.subcategories:
            candidate_sets.append(MameCategoryFilterService.matching_machine_names({"categories": state.categories, "subcategories": state.subcategories}, database_path()))

        queries = {key: str(getattr(state, key, "") or "").strip().casefold() for key in ("title_query", "full_text", "rom_query", "parent_query", "clone_query", "video_query", "audio_query", "screen_query", "cabinet_query", "channels_query")}
        type_filter = str(getattr(state, "type_filter", "all") or "all"); orientation = str(getattr(state, "orientation", "all") or "all").casefold(); year_from = getattr(state, "year_from", None); year_to = getattr(state, "year_to", None)

        def match(game: ArcadeGame) -> bool:
            meta = cls._metadata_text(game)
            if queries["title_query"] and queries["title_query"] not in f"{game.machine_name} {game.display_name}".casefold(): return False
            if queries["full_text"] and queries["full_text"] not in meta: return False
            if queries["rom_query"]:
                rom_text = " ".join(str(game.metadata.get(key, "")) for key in ("rom", "rom_name", "filename", "file"))
                if queries["rom_query"] not in rom_text.casefold(): return False
            parent = str(game.parent_name or game.metadata.get("cloneof") or "").casefold()
            if queries["parent_query"] and queries["parent_query"] not in parent: return False
            if queries["clone_query"] and queries["clone_query"] not in game.machine_name.casefold(): return False
            if type_filter == "parent" and game.is_clone: return False
            if type_filter == "clone" and not game.is_clone: return False
            year = cls._year(game)
            if year_from is not None and (year is None or year < int(year_from)): return False
            if year_to is not None and (year is None or year > int(year_to)): return False
            for key in ("video_query", "audio_query", "screen_query", "cabinet_query", "channels_query"):
                if queries[key] and queries[key] not in meta: return False
            if orientation != "all" and orientation not in meta: return False
            return True

        if any(queries.values()) or type_filter != "all" or year_from is not None or year_to is not None:
            candidate_sets.append({game.machine_name for game in games if match(game)})
        if not candidate_sets: return None
        result = candidate_sets[0].copy()
        for names in candidate_sets[1:]: result.intersection_update(names)
        return result

    @classmethod
    def _rules(cls, state, games: list[ArcadeGame] | None = None) -> FilterRules:
        excluded_content = set()
        for key, types in cls._CONTENT.items():
            if bool(state.fundamental.get(key, False)): excluded_content.update(types)
        excluded_genres = {ArcadeGenre.DANCE} if bool(state.fundamental.get("dance", False)) else set()
        def enum(values, enum_type):
            allowed = {member.value for member in enum_type}; return {enum_type(value) for value in values if value in allowed}
        candidate_names = cls._candidate_names(games or [], state) if games is not None else None
        included_content = set(enum(state.content, ArcadeContentType))
        if bool(getattr(state, "mamecab_only", True)): included_content.add(ArcadeContentType.ARCADE)
        return FilterRules(
            included_machine_names=frozenset(candidate_names) if candidate_names is not None else frozenset(), excluded_content_types=frozenset(excluded_content), excluded_genres=frozenset(excluded_genres), included_content_types=frozenset(included_content),
            included_playability=frozenset(enum(state.playability, PlayabilityStatus)), included_genres=frozenset(enum(state.genre, ArcadeGenre)), included_hardware=frozenset(enum(state.hardware, ArcadeHardwareFamily)), included_manufacturers=frozenset(state.manufacturer), included_series=frozenset(state.series), included_inputs=frozenset(enum(state.input, ArcadeInputType)), included_wheel_angles=frozenset(enum(state.wheel, WheelAngleClass)),
            include_bios=state.mame_include_bios, include_devices=state.mame_include_devices, include_optional=state.mame_include_optional, working_only=state.mame_working_only, parents_only=state.mame_clone_policy == "parents_only",
        )

    @classmethod
    def _result(cls, path: Path, state):
        payload = cls._payload(path); games = cls._games(payload); return payload, games, ArcadeFilterEngine().apply(games, cls._rules(state, games))

    @classmethod
    def preview(cls, path: Path, state) -> dict:
        _, _, result = cls._result(path, state); reasons = Counter(item.trace.rule or item.trace.stage.value for item in result.excluded)
        return {"unit": "machines", "input_count": result.total_input, "output_count": result.included_count, "filtered_count": result.excluded_count, "filter_counts": dict(reasons), "stage_counts": {stage.value: count for stage, count in result.counts_after_stage.items()}}

    @classmethod
    def apply(cls, path: Path, state) -> dict:
        payload, _, result = cls._result(path, state); kept_names = {item.game.machine_name for item in result.games}; evidence = list(payload.get("evidence", [])); kept_evidence = [item for item in evidence if str(item.get("machine_name") or item.get("machine") or item.get("name") or "") in kept_names]
        reasons = Counter(item.trace.rule or item.trace.stage.value for item in result.excluded); run_id = uuid4().hex[:16]; out_dir = scans_root() / "filtered" / "mame"; out_dir.mkdir(parents=True, exist_ok=True)
        label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(payload.get("catalog_label") or "catalog")); output_path = out_dir / f"MAME_{label}_{payload.get('scan_type', 'arcade')}_FILTER_{run_id}.json"
        output = {"format": "SERM-FILTER-V2", "schema_version": 2, "filter_run_id": run_id, "scan_id": payload.get("scan_id"), "profile_id": state.profile_id, "source": "mame", "system": payload.get("system"), "scan_type": payload.get("scan_type", "arcade"), "catalog_label": payload.get("catalog_label"), "catalog_hash": payload.get("catalog_hash"), "source_scan_file": str(path.resolve()), "created_at": time.time(), "unit": "machines", "input_count": result.total_input, "output_count": result.included_count, "filtered_count": result.excluded_count, "physical_evidence_count": len(kept_evidence), "filter_counts": dict(reasons), "stage_counts": {stage.value: count for stage, count in result.counts_after_stage.items()}, "filters": asdict(state), "machines": sorted(kept_names), "evidence": kept_evidence, "output_file": str(output_path)}
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"); output["filtered_file_path"] = str(output_path); return output


__all__ = ["MameFilterV2Service"]
