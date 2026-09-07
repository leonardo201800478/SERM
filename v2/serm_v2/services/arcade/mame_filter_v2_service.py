"""Serviço de filtros MAME V2 orientado ao catálogo relacional do SERM."""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from ...models.arcade import ArcadeGame, ArcadePlatform, PlayabilityStatus
from ...models.arcade_classification import ArcadeContentType, ArcadeGenre, ArcadeHardwareFamily, ArcadeInputType, WheelAngleClass
from ...runtime.paths import data_root, database_path, scans_root
from ..arcade.filter_engine import ArcadeFilterEngine, FilterRules
from ..mame_category_filter_service import MameCategoryFilterService
from ..mame_folder_filter_service import MameFolderFilterService
from ..scan_file_repository import ScanFileRepository


class MameFilterV2Service:
    """Usa o ListXML normalizado no ``serm.db`` como fonte primária do filtro."""

    _SQLITE_VARIABLE_CHUNK = 500
    _CONTENT = {
        "mechanical": {ArcadeContentType.MECHANICAL, ArcadeContentType.ELECTROMECHANICAL},
        "console": {ArcadeContentType.CONSOLE},
        "handheld": {ArcadeContentType.HANDHELD},
        "fruit_machines": {ArcadeContentType.FRUIT_MACHINE, ArcadeContentType.GAMBLING, ArcadeContentType.CASINO, ArcadeContentType.REDEMPTION, ArcadeContentType.MEDAL},
        "quiz": {ArcadeContentType.QUIZ},
        "tabletop": {ArcadeContentType.TABLETOP, ArcadeContentType.MAHJONG},
    }
    _FOLDER_FILES = {
        "working": ("Working Arcade.ini", "Working Arcade Clean.ini"),
        "not_working": ("Not Working Arcade.ini", "not_working_arcade.ini"),
        "parents": ("Parents Arcade.ini", "parents_arcade.ini"),
        "clones": ("Clones Arcade.ini",),
        "mechanical": ("Mechanical Arcade.ini", "mechanical_arcade.ini"),
        "non_mechanical": ("Non Mechanical Arcade.ini", "not_mechanical_arcade.ini"),
        "chd": ("CHD Working.ini", "CHD (no BIOS).ini"),
        "freeplay": ("freeplay.ini",),
        "screenless": ("screenless.ini",),
        "mature": ("mature.ini", "not_mature.ini"),
        "genre": ("genre.ini",),
        "series": ("series.ini",),
        "languages": ("languages.ini",),
        "driver": ("driver.ini",),
        "controls": ("controls.ini", "Control.ini"),
        "cpu": ("CPU.ini",),
        "device": ("Device.ini",),
        "resolution": ("resolution.ini",),
        "screen": ("Screen.ini",),
        "sound": ("Sound.ini",),
        "version": ("Version.ini", "version_NEW.ini", "version_ON.ini"),
        "vsync": ("Vsync.ini",),
        "category": ("category.ini",),
        "catlist": ("catlist.ini",),
        "bootlegs": ("bootlegs.ini", "Non Bootlegs.ini", "not_ bootlegs.ini"),
        "artwork": ("artwork.ini", "artwork_necessary.ini"),
        "players": ("players.ini",),
        "multiplayer": ("multiplayer.ini",),
        "prototype": ("prototype.ini",),
        "game_or_no_game": ("Game Or No Game.ini",),
    }

    @classmethod
    def _ensure_folder_filters(cls) -> None:
        """Sincroniza rapidamente os INIs: arquivos inalterados são apenas ignorados."""
        try:
            paths_file = data_root() / "emulator_paths.json"
            payload = json.loads(paths_file.read_text(encoding="utf-8"))
            executable = payload.get("mame_executable")
            if isinstance(executable, str) and executable.strip():
                result = MameFolderFilterService(
                    database_path(), Path(executable).expanduser().resolve().parent
                ).ingest()
                if result.get("files") or result.get("entries"):
                    return
        except (OSError, ValueError, TypeError, sqlite3.Error):
            return

    @classmethod
    def _payload(cls, path: Path) -> dict:
        payload = ScanFileRepository.load(path)
        if str(payload.get("source", "")).casefold() != "mame":
            raise ValueError("O snapshot selecionado não é um scan MAME.")
        return payload

    @classmethod
    def _import_id(cls, connection: sqlite3.Connection, payload: dict) -> tuple[int, str | None]:
        source_hash = str(payload.get("catalog_hash") or "").strip()
        if source_hash:
            row = connection.execute("SELECT id,mame_build FROM mame_listxml_import WHERE source_hash=? AND status='completed' ORDER BY id DESC LIMIT 1", (source_hash,)).fetchone()
            if row:
                return int(row[0]), row[1]
        label = str(payload.get("catalog_label") or "")
        build_match = re.search(r"(?:MAME\s*)?([0-9]+\.[0-9]+)", label, re.IGNORECASE)
        if build_match:
            row = connection.execute("SELECT id,mame_build FROM mame_listxml_import WHERE mame_build LIKE ? AND status='completed' ORDER BY id DESC LIMIT 1", (f"%{build_match.group(1)}%",)).fetchone()
            if row:
                return int(row[0]), row[1]
        row = connection.execute("SELECT id,mame_build FROM mame_listxml_import WHERE status='completed' ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            return int(row[0]), row[1]
        raise ValueError("Nenhuma importação ListXML MAME concluída foi encontrada no SERM.")

    @staticmethod
    def _mame_flag(value: object) -> bool:
        """Normaliza flags do ListXML que podem chegar como yes/no, 1/0 ou bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value or "").strip().casefold() in {"yes", "true", "1", "on"}

    @classmethod
    def _games(cls, payload: dict) -> list[ArcadeGame]:
        cls._ensure_folder_filters()
        physical_names = {str(item.get("machine_name") or item.get("machine") or item.get("name") or "").strip() for item in payload.get("evidence", [])}
        physical_names.discard("")
        if not physical_names:
            return []
        with sqlite3.connect(database_path(), timeout=60.0) as db:
            import_id, _build = cls._import_id(db, payload)
            machine_names = sorted(physical_names)
            rows = []
            for start in range(0, len(machine_names), cls._SQLITE_VARIABLE_CHUNK):
                chunk = machine_names[start : start + cls._SQLITE_VARIABLE_CHUNK]
                placeholders = ",".join("?" for _ in chunk)
                query = f"""
                    SELECT m.id,m.name,m.cloneof,m.romof,m.isbios,m.isdevice,m.ismechanical,m.runnable,m.description,m.year,m.manufacturer,m.sourcefile,
                           GROUP_CONCAT(DISTINCT c.category),GROUP_CONCAT(DISTINCT c.subcategory),MAX(d.status),MAX(d.emulation),MAX(d.sound),MAX(d.graphic),GROUP_CONCAT(DISTINCT disp.type),GROUP_CONCAT(DISTINCT disp.rotate),GROUP_CONCAT(DISTINCT disp.width || 'x' || disp.height),GROUP_CONCAT(DISTINCT disp.refresh_raw),GROUP_CONCAT(DISTINCT ctl.type),MAX(ctl.buttons),MAX(inp.players),GROUP_CONCAT(DISTINCT chip.type || ':' || COALESCE(chip.name,'')),COUNT(DISTINCT disk.id),COUNT(DISTINCT sample.id),COUNT(DISTINCT bios.id),COUNT(DISTINCT device.id),GROUP_CONCAT(DISTINCT rom.name),GROUP_CONCAT(DISTINCT disk.name)
                    FROM mame_machine m LEFT JOIN mame_classification c ON c.machine_id=m.id AND c.resolved_status='resolved' LEFT JOIN mame_driver d ON d.machine_id=m.id LEFT JOIN mame_display disp ON disp.machine_id=m.id LEFT JOIN mame_input inp ON inp.machine_id=m.id LEFT JOIN mame_control ctl ON ctl.input_id=inp.id LEFT JOIN mame_chip chip ON chip.machine_id=m.id LEFT JOIN mame_disk disk ON disk.machine_id=m.id LEFT JOIN mame_sample sample ON sample.machine_id=m.id LEFT JOIN mame_biosset bios ON bios.machine_id=m.id LEFT JOIN mame_device device ON device.machine_id=m.id LEFT JOIN mame_rom rom ON rom.machine_id=m.id
                    WHERE m.import_id=? AND m.name IN ({placeholders}) GROUP BY m.id ORDER BY m.name COLLATE NOCASE
                """
                rows.extend(db.execute(query, (import_id, *chunk)).fetchall())
            folder_maps = cls._folder_maps(db, physical_names)
            games: list[ArcadeGame] = []
            for row in rows:
                (machine_id,name,cloneof,romof,isbios,isdevice,ismechanical,runnable,description,year,manufacturer,sourcefile,categories,subcategories,driver_status,emulation,sound,graphic,display_types,rotates,resolutions,refreshes,controls,buttons,players,chips,disk_count,sample_count,bios_count,device_count,rom_names,disk_names) = row
                is_bios = cls._mame_flag(isbios)
                is_device = cls._mame_flag(isdevice)
                is_mechanical = cls._mame_flag(ismechanical)
                category_values = [v.strip() for v in str(categories or "").split(",") if v.strip()]
                subcategory_values = [v.strip() for v in str(subcategories or "").split(",") if v.strip()]
                non_arcade_categories = {"console", "computer", "handheld", "pachinko", "pachislot"}
                if not is_bios and not is_device and not is_mechanical and not any(v.casefold() in non_arcade_categories for v in category_values):
                    category_values.append("arcade")
                folder_filters = {key: sorted(values.get(name, set())) for key, values in folder_maps.items()}
                genre_values = folder_filters.get("genre", [])
                series_values = folder_filters.get("series", [])
                working = bool(folder_filters.get("working")) and not bool(folder_filters.get("not_working"))
                if not folder_filters.get("working") and not folder_filters.get("not_working"):
                    working = str(runnable or "").casefold() in {"yes", "true", "1"}
                status = str(driver_status or "").casefold()
                emu = str(emulation or "").casefold()
                if working:
                    playability = PlayabilityStatus.FULLY_PLAYABLE.value
                elif status == "good" and emu == "good":
                    playability = PlayabilityStatus.FUNCTIONAL.value
                elif status == "imperfect" or emu == "imperfect":
                    playability = PlayabilityStatus.PARTIALLY_PLAYABLE.value
                elif status == "preliminary" or emu == "preliminary":
                    playability = PlayabilityStatus.IN_DEVELOPMENT.value
                elif status == "bad" or emu == "bad":
                    playability = PlayabilityStatus.UNPLAYABLE.value
                else:
                    playability = PlayabilityStatus.UNKNOWN.value
                metadata = {
                    "year": year, "manufacturer": manufacturer, "sourcefile": sourcefile,
                    "categories": category_values, "subcategories": subcategory_values,
                    "driver_status": driver_status, "emulation": emulation, "sound": sound, "graphic": graphic,
                    "display": display_types, "rotate": rotates, "resolution": resolutions, "refresh": refreshes,
                    "controls": controls, "buttons": buttons, "players": players, "chips": chips,
                    "rom_names": rom_names, "disk_names": disk_names, "disk_count": int(disk_count or 0),
                    "sample_count": int(sample_count or 0), "bios_count": int(bios_count or 0), "device_count": int(device_count or 0),
                    "is_bios": is_bios, "is_device": is_device, "ismechanical": is_mechanical, "runnable": runnable,
                    "working": working, "playability": playability, "genres": genre_values,
                    "series": series_values[0] if series_values else None, "folder_filters": folder_filters,
                }
                games.append(ArcadeGame(machine_name=str(name), display_name=str(description or name), platform=ArcadePlatform.MAME, parent_name=str(cloneof) if cloneof else None, category=category_values[0] if category_values else None, subcategory=subcategory_values[0] if subcategory_values else None, metadata=metadata))
            return games

    @classmethod
    def _folder_maps(cls, db: sqlite3.Connection, machine_names: set[str]) -> dict[str, dict[str, set[str]]]:
        result = {key: {} for key in cls._FOLDER_FILES}
        if not machine_names:
            return result
        machine_names_sorted = sorted(machine_names)
        source_rows = db.execute("SELECT id,file_name FROM mame_folder_filter_source").fetchall()
        source_by_key = {key: set() for key in cls._FOLDER_FILES}
        for source_id, file_name in source_rows:
            lowered = str(file_name).casefold()
            for key, names in cls._FOLDER_FILES.items():
                if lowered in {name.casefold() for name in names}:
                    source_by_key[key].add(int(source_id))
        for key, ids in source_by_key.items():
            if not ids:
                continue
            placeholders_ids = ",".join("?" for _ in ids)
            for start in range(0, len(machine_names_sorted), cls._SQLITE_VARIABLE_CHUNK - len(ids)):
                chunk = machine_names_sorted[start : start + (cls._SQLITE_VARIABLE_CHUNK - len(ids))]
                if not chunk:
                    continue
                placeholders_names = ",".join("?" for _ in chunk)
                rows = db.execute(f"SELECT machine_name,COALESCE(section,'') FROM mame_folder_filter_entry WHERE source_id IN ({placeholders_ids}) AND machine_name IN ({placeholders_names})", (*sorted(ids), *chunk)).fetchall()
                mapping = result[key]
                for machine_name, section in rows:
                    mapping.setdefault(str(machine_name), set()).add(str(section))
        return result

    @classmethod
    def facets(cls, path: Path) -> dict[str, list[dict[str, object]]]:
        games = cls._games(cls._payload(path))
        classifier = ArcadeFilterEngine()._classifier
        counters = {key: Counter() for key in ("year", "content", "playability", "genre", "hardware", "manufacturer", "series", "input", "wheel")}
        for game in games:
            classification = classifier.classify(game)
            if classification.content_type is ArcadeContentType.ARCADE:
                year = cls._year(game)
                if year is not None:
                    counters["year"][str(year)] += 1
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
        match = re.search(r"(?:19|20)\d{2}", str(game.metadata.get("year") or ""))
        return int(match.group()) if match else None

    @staticmethod
    def _is_arcade(game: ArcadeGame) -> bool:
        return ArcadeFilterEngine()._classifier.classify(game).content_type is ArcadeContentType.ARCADE

    @staticmethod
    def _is_horizontal(game: ArcadeGame) -> bool:
        rotate = str(game.metadata.get("rotate") or "").casefold()
        display = str(game.metadata.get("display") or "").casefold()
        if any(value in rotate for value in ("90", "270", "vertical")):
            return False
        if "vertical" in display or "tate" in display:
            return False
        return True

    @staticmethod
    def _is_vertical(game: ArcadeGame) -> bool:
        return not MameFilterV2Service._is_horizontal(game)

    @classmethod
    def _candidate_names(cls, games: list[ArcadeGame], state) -> set[str] | None:
        candidate_sets: list[set[str]] = []
        game_names = {game.machine_name for game in games}
        if state.categories or state.subcategories:
            names = MameCategoryFilterService.matching_machine_names({"categories": state.categories, "subcategories": state.subcategories}, database_path())
            candidate_sets.append(names.intersection(game_names))
        queries = {key: str(getattr(state, key, "") or "").strip().casefold() for key in ("title_query", "full_text", "rom_query", "parent_query", "clone_query", "video_query", "audio_query", "screen_query", "cabinet_query", "channels_query")}
        type_filter = str(getattr(state, "type_filter", "all") or "all")
        year_from, year_to = getattr(state, "year_from", None), getattr(state, "year_to", None)
        orientation = str(getattr(state, "orientation", "all") or "all").casefold()
        def match(game: ArcadeGame) -> bool:
            meta = cls._metadata_text(game)
            if queries["title_query"] and queries["title_query"] not in f"{game.machine_name} {game.display_name}".casefold(): return False
            if queries["full_text"] and queries["full_text"] not in meta: return False
            if queries["rom_query"] and queries["rom_query"] not in str(game.metadata.get("rom_names", "")).casefold(): return False
            if queries["parent_query"] and queries["parent_query"] not in str(game.parent_name or "").casefold(): return False
            if queries["clone_query"] and queries["clone_query"] not in game.machine_name.casefold(): return False
            if type_filter == "parent" and game.is_clone: return False
            if type_filter == "clone" and not game.is_clone: return False
            year = cls._year(game)
            if year_from is not None or year_to is not None:
                if not cls._is_arcade(game) or year is None: return False
                if year_from is not None and year < int(year_from): return False
                if year_to is not None and year > int(year_to): return False
            if orientation == "horizontal" and not cls._is_horizontal(game): return False
            if orientation == "vertical" and not cls._is_vertical(game): return False
            for key in ("video_query", "audio_query", "screen_query", "cabinet_query", "channels_query"):
                if queries[key] and queries[key] not in meta: return False
            return True
        if any(queries.values()) or type_filter != "all" or year_from is not None or year_to is not None or orientation != "all":
            candidate_sets.append({game.machine_name for game in games if match(game)})
        if not candidate_sets:
            return None
        result = candidate_sets[0].copy()
        for names in candidate_sets[1:]: result.intersection_update(names)
        return result

    @classmethod
    def _rules(cls, state, games: list[ArcadeGame] | None = None) -> FilterRules:
        excluded_content = set()
        for key, types in cls._CONTENT.items():
            if bool(state.fundamental.get(key, False)):
                excluded_content.update(types)
        excluded_genres = {ArcadeGenre.DANCE} if bool(state.fundamental.get("dance", False)) else set()
        def enum(values, enum_type):
            allowed = {member.value for member in enum_type}
            return {enum_type(value) for value in values if value in allowed}
        candidate_names = cls._candidate_names(games or [], state) if games is not None else None
        included_content = set(enum(state.content, ArcadeContentType))
        if bool(getattr(state, "mamecab_only", True)):
            included_content.add(ArcadeContentType.ARCADE)
        return FilterRules(
            included_machine_names=frozenset(candidate_names) if candidate_names is not None else frozenset(),
            excluded_content_types=frozenset(excluded_content),
            excluded_genres=frozenset(excluded_genres),
            included_content_types=frozenset(included_content),
            included_playability=frozenset(enum(state.playability, PlayabilityStatus)),
            included_genres=frozenset(enum(state.genre, ArcadeGenre)),
            included_hardware=frozenset(enum(state.hardware, ArcadeHardwareFamily)),
            included_manufacturers=frozenset(state.manufacturer),
            included_series=frozenset(state.series),
            included_inputs=frozenset(enum(state.input, ArcadeInputType)),
            included_wheel_angles=frozenset(enum(state.wheel, WheelAngleClass)),
            include_bios=state.mame_include_bios, include_devices=state.mame_include_devices,
            include_optional=state.mame_include_optional, working_only=state.mame_working_only,
            parents_only=state.mame_clone_policy == "parents_only",
        )

    @classmethod
    def _result(cls, path: Path, state):
        payload = cls._payload(path)
        games = cls._games(payload)
        return payload, games, ArcadeFilterEngine().apply(games, cls._rules(state, games))

    @classmethod
    def preview(cls, path: Path, state) -> dict:
        _, _, result = cls._result(path, state)
        reasons = Counter(item.trace.rule or item.trace.stage.value for item in result.excluded)
        return {"unit": "machines", "input_count": result.total_input, "output_count": result.included_count, "filtered_count": result.excluded_count, "filter_counts": dict(reasons), "stage_counts": {stage.value: count for stage, count in result.counts_after_stage.items()}}

    @classmethod
    def apply(cls, path: Path, state) -> dict:
        payload, _, result = cls._result(path, state)
        kept_names = {item.game.machine_name for item in result.games}
        evidence = list(payload.get("evidence", []))
        kept_evidence = [item for item in evidence if str(item.get("machine_name") or item.get("machine") or item.get("name") or "") in kept_names]
        reasons = Counter(item.trace.rule or item.trace.stage.value for item in result.excluded)
        run_id = uuid4().hex[:16]
        out_dir = scans_root() / "filtered" / "mame"
        out_dir.mkdir(parents=True, exist_ok=True)
        label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(payload.get("catalog_label") or "catalog"))
        output_path = out_dir / f"MAME_{label}_{payload.get('scan_type', 'arcade')}_FILTER_{run_id}.json"
        output = {
            "format": "SERM-FILTER-V2", "schema_version": 2, "filter_run_id": run_id,
            "scan_id": payload.get("scan_id"), "profile_id": state.profile_id, "source": "mame",
            "system": payload.get("system"), "scan_type": payload.get("scan_type", "arcade"),
            "catalog_label": payload.get("catalog_label"), "catalog_hash": payload.get("catalog_hash"),
            "source_scan_file": str(path.resolve()), "created_at": time.time(), "unit": "machines",
            "input_count": result.total_input, "output_count": result.included_count, "filtered_count": result.excluded_count,
            "physical_evidence_count": len(kept_evidence), "filter_counts": dict(reasons),
            "stage_counts": {stage.value: count for stage, count in result.counts_after_stage.items()},
            "filters": asdict(state), "machines": sorted(kept_names), "evidence": kept_evidence, "output_file": str(output_path),
        }
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        output["filtered_file_path"] = str(output_path)
        return output


__all__ = ["MameFilterV2Service"]
