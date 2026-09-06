"""Filtros específicos para snapshots No-Intro.

A regra de seleção usa somente metadados coletados no scan. O DAT continua
sendo a autoridade para hashes; variantes externas (translation/hack) podem
ser mantidas por nome, mas nunca são tratadas como dumps verificados.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from uuid import uuid4

from ..runtime.paths import scans_root
from .scan_file_repository import ScanFileRepository


DEFAULT_REGION_PRIORITY = (
    "Brazil",
    "Portugal",
    "USA/America",
    "World",
    "Europe",
    "Spain",
    "Japan",
    "China",
    "Korea",
    "Others",
)


def _tags(item: dict) -> set[str]:
    return {str(value).casefold() for value in (item.get("categories") or [])}


def _values(item: dict, prefix: str) -> list[str]:
    return [tag[len(prefix) :] for tag in _tags(item) if tag.startswith(prefix)]


class NoIntroFilterService:
    """Aplica conteúdo, clones, regiões e 1G1R sem alterar o scan bruto."""

    VALID_STATUSES = frozenset({"CURRENT", "DUPLICATE", "UNVERIFIED_VARIANT"})

    @classmethod
    def preview(cls, scan_path: Path, profile) -> dict:
        payload = ScanFileRepository.load(scan_path)
        kept, reasons = cls._filter(payload.get("evidence", []), profile)
        return {
            "input_count": len(payload.get("evidence", [])),
            "output_count": len(kept),
            "filtered_count": len(payload.get("evidence", [])) - len(kept),
            "filter_counts": dict(reasons),
            "catalog_label": payload.get("catalog_label"),
        }

    @classmethod
    def apply(cls, scan_path: Path, profile) -> dict:
        payload = ScanFileRepository.load(scan_path)
        if str(payload.get("source", "")).casefold() != "no-intro":
            raise ValueError("Os filtros No-Intro só podem ser aplicados a um scan No-Intro.")
        evidence = list(payload.get("evidence", []))
        kept, reasons = cls._filter(evidence, profile)
        run_id = uuid4().hex[:16]
        out_dir = scans_root() / "filtered" / "no_intro"
        out_dir.mkdir(parents=True, exist_ok=True)
        label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(payload.get("catalog_label") or "catalog"))
        out = out_dir / f"No-Intro_{label}_FILTER_{run_id}.json"
        region_priority = list(getattr(profile, "region_priority", ()) or DEFAULT_REGION_PRIORITY)
        result = {
            "format": "SERM-FILTER-V1",
            "filter_run_id": run_id,
            "scan_id": payload.get("scan_id"),
            "profile_id": str(profile.profile_id),
            "source": payload.get("source"),
            "system": payload.get("system"),
            "scan_type": payload.get("scan_type", "full"),
            "catalog_label": payload.get("catalog_label"),
            "catalog_hash": payload.get("catalog_hash"),
            "source_scan_file": str(scan_path),
            "created_at": time.time(),
            "input_count": len(evidence),
            "output_count": len(kept),
            "filtered_count": len(evidence) - len(kept),
            "filter_counts": dict(reasons),
            "filters": cls.profile_payload(profile, region_priority),
            "evidence": kept,
        }
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        result["filtered_file_path"] = str(out)
        return result

    @classmethod
    def profile_payload(cls, profile, region_priority: list[str]) -> dict:
        return {
            "include_bios": bool(getattr(profile, "include_bios", False)),
            "include_demos": bool(getattr(profile, "include_demos", False)),
            "include_prototypes": bool(getattr(profile, "include_prototypes", False)),
            "include_betas": bool(getattr(profile, "include_betas", False)),
            "include_programs": bool(getattr(profile, "include_programs", False)),
            "include_np": bool(getattr(profile, "include_np", False)),
            "include_samples": bool(getattr(profile, "include_samples", False)),
            "include_aftermarket": bool(getattr(profile, "include_aftermarket", False)),
            "include_unlicensed": bool(getattr(profile, "include_unlicensed", False)),
            "include_clones": bool(getattr(profile, "include_clones", True)),
            "one_game_one_region": bool(getattr(profile, "one_game_one_region", False)),
            "region_priority": region_priority,
            "include_translations": bool(getattr(profile, "include_translations", False)),
            "include_hacks": bool(getattr(profile, "include_hacks", False)),
            "keep_unverified_variants": bool(getattr(profile, "keep_unverified_variants", True)),
            "remove_previous_versions": bool(getattr(profile, "remove_previous_versions", True)),
        }

    @classmethod
    def _filter(cls, evidence: list[dict], profile) -> tuple[list[dict], Counter]:
        reasons: Counter = Counter()
        candidates: list[dict] = []
        for item in evidence:
            reason = cls._reject_reason(item, profile)
            if reason:
                reasons[reason] += 1
                continue
            candidates.append(item)

        if not bool(getattr(profile, "one_game_one_region", False)):
            return candidates, reasons

        selected: list[dict] = []
        groups: dict[str, list[dict]] = {}
        for item in candidates:
            groups.setdefault(cls._family_key(item), []).append(item)
        for group in groups.values():
            chosen = cls._choose_1g1r(group, profile)
            if chosen is None:
                reasons["no_1g1r_candidate"] += 1
                continue
            selected.append(chosen)
            for item in group:
                if item is not chosen:
                    reasons["1g1r"] += 1
        return selected, reasons

    @classmethod
    def _reject_reason(cls, item: dict, profile) -> str | None:
        status = str(item.get("status") or "").upper()
        if status not in cls.VALID_STATUSES:
            return status.lower() or "invalid_status"

        tags = _tags(item)
        if status == "UNVERIFIED_VARIANT":
            if not bool(getattr(profile, "keep_unverified_variants", True)):
                return "unverified"
            if "variant:translation" in tags and not bool(getattr(profile, "include_translations", False)):
                return "translation"
            if "variant:hack" in tags and not bool(getattr(profile, "include_hacks", False)):
                return "hack"

        checks = (
            ("type:bios", "include_bios", "bios"),
            ("type:demo", "include_demos", "demo"),
            ("type:proto", "include_prototypes", "prototype"),
            ("type:beta", "include_betas", "beta"),
            ("type:program", "include_programs", "program"),
            ("type:np", "include_np", "np"),
            ("type:sample", "include_samples", "sample"),
            ("type:aftermarket", "include_aftermarket", "aftermarket"),
            ("type:unlicensed", "include_unlicensed", "unlicensed"),
        )
        for tag, option, reason in checks:
            if tag in tags and not bool(getattr(profile, option, False)):
                return reason

        if "variant:translation" in tags and not bool(getattr(profile, "include_translations", False)):
            return "translation"
        if "variant:hack" in tags and not bool(getattr(profile, "include_hacks", False)):
            return "hack"
        if "clone:yes" in tags and not bool(getattr(profile, "include_clones", True)):
            return "clone"
        return None

    @staticmethod
    def _family_key(item: dict) -> str:
        cloneof = str(item.get("cloneof") or "").strip()
        if cloneof:
            return cloneof.casefold()
        base = str(item.get("merge_name") or item.get("machine_name") or "").strip()
        return re.sub(r"\s+", " ", base).casefold()

    @classmethod
    def _choose_1g1r(cls, group: list[dict], profile) -> dict | None:
        priority = list(getattr(profile, "region_priority", ()) or DEFAULT_REGION_PRIORITY)
        ranks = {str(name).casefold(): index for index, name in enumerate(priority)}
        best: tuple[tuple, dict] | None = None
        for item in group:
            regions = [value.casefold() for value in _values(item, "region:")]
            region_rank = cls._region_rank(regions, ranks)
            if region_rank >= len(priority) + 1:
                region_rank = len(priority)
            tags = _tags(item)
            unverified = 1 if str(item.get("status")).upper() == "UNVERIFIED_VARIANT" else 0
            prerelease = int(any(tag in tags for tag in ("type:beta", "type:proto", "type:demo", "type:sample")))
            version_penalty = 1 if "version:" in " ".join(tags) else 0
            language_penalty = 0 if "language:en" in tags else 1
            score = (region_rank, unverified, prerelease, language_penalty, version_penalty, str(item.get("machine_name") or "").casefold())
            if best is None or score < best[0]:
                best = (score, item)
        return best[1] if best else None

    @staticmethod
    def _region_rank(regions: list[str], ranks: dict[str, int]) -> int:
        if not regions:
            return len(ranks) + 1
        values: list[int] = []
        for region in regions:
            aliases = {
                "bra": "brazil", "brazil": "brazil",
                "por": "portugal", "portugal": "portugal",
                "usa": "usa/america", "america": "usa/america",
                "eur": "europe", "europe": "europe",
                "spa": "spain", "spain": "spain",
                "jpn": "japan", "japan": "japan",
                "chn": "china", "china": "china",
                "kor": "korea", "korea": "korea",
                "world": "world",
            }
            canonical = aliases.get(region, "others")
            values.append(ranks.get(canonical, ranks.get("others", len(ranks))))
        return min(values)


__all__ = ["DEFAULT_REGION_PRIORITY", "NoIntroFilterService"]
