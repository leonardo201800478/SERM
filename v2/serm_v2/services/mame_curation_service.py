"""Integração da curadoria de domínio ao pipeline de filtros MAME V2."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from ..domain.curation import CurationPolicy, CurationResult, curate_games
from .arcade.mame_filter_v2_service import MameFilterV2Service
from .scan_file_repository import ScanFileRepository


class MameCurationService:
    """Aplica curadoria sobre o catálogo normalizado antes do filtro físico."""

    @staticmethod
    def policy_from_profile(profile, values: dict | None = None) -> CurationPolicy:
        values = values or {}

        def value(name: str, default):
            if name in values:
                return values[name]
            return getattr(profile, name, default)

        def integer(name: str):
            raw = value(name, None)
            if raw in (None, "", 0):
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None

        def number(name: str):
            raw = value(name, None)
            if raw in (None, ""):
                return None
            try:
                return float(raw)
            except (TypeError, ValueError):
                return None

        def strings(name: str) -> tuple[str, ...]:
            raw = value(name, ())
            if isinstance(raw, str):
                return tuple(item.strip() for item in raw.split(",") if item.strip())
            return tuple(str(item).strip() for item in (raw or ()) if str(item).strip())

        return CurationPolicy(
            preferred_regions=strings("curation_preferred_regions"),
            preferred_languages=strings("curation_preferred_languages"),
            max_players=integer("curation_max_players"),
            max_buttons=integer("curation_max_buttons"),
            required_controls=strings("curation_required_controls"),
            required_directions=strings("curation_required_directions"),
            strict_controls=bool(value("curation_strict_controls", False)),
            orientation=str(value("curation_orientation", "both") or "both"),
            include_clones=bool(value("curation_include_clones", True)),
            include_bootlegs=bool(value("curation_include_bootlegs", True)),
            include_prototypes=bool(value("curation_include_prototypes", True)),
            one_game_one_rom=bool(value("curation_one_game_one_rom", False)),
            min_quality_score=number("curation_min_quality_score"),
        )

    @classmethod
    def curate_payload(cls, payload: dict, profile, values: dict | None = None) -> CurationResult:
        games = MameFilterV2Service._games(payload)
        return curate_games(games, cls.policy_from_profile(profile, values))

    @classmethod
    def prepare_scan(
        cls, scan_path: Path, profile, values: dict | None = None
    ) -> tuple[Path, CurationResult]:
        payload = ScanFileRepository.load(scan_path)
        if str(payload.get("source", "")).casefold() != "mame":
            raise ValueError("A curadoria MAME exige um snapshot de scan MAME.")

        result = cls.curate_payload(payload, profile, values)
        selected_names = {game.machine_name for game in result.selected}
        evidence = payload.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []

        policy = cls.policy_from_profile(profile, values)
        curated = dict(payload)
        curated["evidence"] = [
            item
            for item in evidence
            if isinstance(item, dict)
            and str(item.get("machine_name") or item.get("machine") or item.get("name") or "").strip()
            in selected_names
        ]
        curated["curation"] = {
            "enabled": True,
            "policy": asdict(policy),
            "selected_games": len(result.selected),
            "input_games": len({str(item.get("machine_name") or "").strip() for item in evidence if isinstance(item, dict)}),
            "excluded_games": len(result.decisions),
            "decisions": [asdict(decision) for decision in result.decisions],
        }

        fd, raw_path = NamedTemporaryFile(
            prefix="serm_mame_curated_",
            suffix=".json",
            delete=False,
            dir=str(scan_path.parent),
            mode="w",
            encoding="utf-8",
        )
        try:
            with fd:
                json.dump(curated, fd, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            Path(raw_path).unlink(missing_ok=True)
            raise
        return Path(raw_path), result


__all__ = ["MameCurationService"]
