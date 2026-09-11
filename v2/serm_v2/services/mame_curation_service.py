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
    """Aplica curadoria sobre o catálogo normalizado antes do filtro físico.

    O snapshot original nunca é alterado. A curadoria cria um snapshot temporário
    contendo apenas as machines selecionadas; o motor de filtros V2 continua
    responsável por regras de ROM, CHD, BIOS, devices e tipo de SET.
    """

    @staticmethod
    def policy_from_profile(profile) -> CurationPolicy:
        return CurationPolicy(
            preferred_regions=tuple(getattr(profile, "curation_preferred_regions", []) or []),
            preferred_languages=tuple(getattr(profile, "curation_preferred_languages", []) or []),
            max_players=getattr(profile, "curation_max_players", None),
            max_buttons=getattr(profile, "curation_max_buttons", None),
            required_controls=tuple(getattr(profile, "curation_required_controls", []) or []),
            required_directions=tuple(getattr(profile, "curation_required_directions", []) or []),
            strict_controls=bool(getattr(profile, "curation_strict_controls", False)),
            orientation=str(getattr(profile, "curation_orientation", "both") or "both"),
            include_clones=bool(getattr(profile, "curation_include_clones", True)),
            include_bootlegs=bool(getattr(profile, "curation_include_bootlegs", True)),
            include_prototypes=bool(getattr(profile, "curation_include_prototypes", True)),
            one_game_one_rom=bool(getattr(profile, "curation_one_game_one_rom", False)),
            min_quality_score=getattr(profile, "curation_min_quality_score", None),
        )

    @classmethod
    def curate_payload(cls, payload: dict, profile) -> CurationResult:
        games = MameFilterV2Service._games(payload)
        return curate_games(games, cls.policy_from_profile(profile))

    @classmethod
    def prepare_scan(cls, scan_path: Path, profile) -> tuple[Path, CurationResult]:
        payload = ScanFileRepository.load(scan_path)
        if str(payload.get("source", "")).casefold() != "mame":
            raise ValueError("A curadoria MAME exige um snapshot de scan MAME.")

        result = cls.curate_payload(payload, profile)
        selected_names = {game.machine_name for game in result.selected}
        evidence = payload.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []

        curated = dict(payload)
        curated["evidence"] = [
            item for item in evidence
            if isinstance(item, dict)
            and str(item.get("machine_name") or item.get("machine") or item.get("name") or "").strip() in selected_names
        ]
        curated["curation"] = {
            "enabled": True,
            "policy": asdict(cls.policy_from_profile(profile)),
            "selected_games": len(result.selected),
            "input_games": len({str(item.get("machine_name") or "").strip() for item in evidence if isinstance(item, dict)}),
            "excluded_games": len(result.decisions),
            "decisions": [asdict(decision) for decision in result.decisions],
        }

        fd, raw_path = NamedTemporaryFile(
            prefix="serm_mame_curated_", suffix=".json", delete=False,
            dir=str(scan_path.parent), mode="w", encoding="utf-8",
        )
        try:
            with fd:
                json.dump(curated, fd, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            Path(raw_path).unlink(missing_ok=True)
            raise
        return Path(raw_path), result


__all__ = ["MameCurationService"]
