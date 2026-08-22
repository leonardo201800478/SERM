"""Serviço central para filtragem de máquinas e importação de categorias."""
import re
import sqlite3
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import xml.etree.ElementTree as ET

from app.core.constants.macro_categories import get_macro_category, macro_sort_key
from app.core.models.filter_profile import FilterCriteria, FilterProfile
from app.core.services.emulator_platform_resolver import EmulatorPlatformResolver
from app.core.services.reconstruction_profiles import ReconstructionTarget
from app.database.repositories.category_repository import CategoryRepository
from app.database.repositories.filter_profile_repository import FilterProfileRepository

logger = logging.getLogger(__name__)


class FilterService:
    """Aplica os filtros persistidos e, opcionalmente, um perfil de emulador."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.category_repo = CategoryRepository(conn)
        self.profile_repo = FilterProfileRepository(conn)
        # Sem manifesto, FBNeo permanece conservador: nenhuma machine é
        # afirmada como FBNeo. O manifesto pode ser carregado posteriormente.
        self.platform_resolver = EmulatorPlatformResolver()

    def load_fbneo_manifest(self, manifest_path: Path) -> None:
        """Carrega o manifesto de machines suportadas pelo FBNeo."""
        self.platform_resolver = EmulatorPlatformResolver.from_manifest(manifest_path)

    # ========================================================================
    # CATEGORIAS
    # ========================================================================

    def get_categories(self) -> List[str]:
        return [cat.name for cat in self.category_repo.get_all()]

    def get_category_display_names(self) -> Dict[str, str]:
        return {cat.name: cat.display_name for cat in self.category_repo.get_all()}

    def get_categories_with_counts(self) -> List[Dict[str, Any]]:
        cursor = self.conn.execute("""
            SELECT c.name, c.display_name, COUNT(mc.machine_id) as count
            FROM category c
            LEFT JOIN machine_category mc ON mc.category_id = c.id
            GROUP BY c.id
            ORDER BY c.display_name
        """)
        rows = cursor.fetchall()
        return [{"name": row[0], "display_name": row[1], "count": row[2]} for row in rows]

    # ========================================================================
    # MACRO CATEGORIAS
    # ========================================================================

    def get_macro_categories_with_counts(self) -> List[Dict[str, Any]]:
        """Agrupa as categorias granulares em macro-grupos."""
        granular = self.get_categories_with_counts()
        groups: Dict[str, Dict[str, Any]] = {}
        for cat in granular:
            macro_name = get_macro_category(cat["name"])
            group = groups.setdefault(
                macro_name, {"macro_name": macro_name, "count": 0, "categories": []},
            )
            group["count"] += cat["count"]
            group["categories"].append(cat["name"])
        return sorted(groups.values(), key=lambda g: macro_sort_key(g["macro_name"]))

    def import_categories_from_ini(self, ini_path: Path) -> Tuple[int, int, List[str]]:
        """Importa categorias usando o parser de ``catver.ini``."""
        return self.import_categories_from_catver(ini_path)

    def import_categories_from_catver(self, catver_path: Path) -> Tuple[int, int, List[str]]:
        if not catver_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {catver_path}")

        UNWANTED_CATEGORIES = {"chd", "devices", "musical", "mature", "mahjong", "screenless", "bios"}

        cursor = self.conn.cursor()
        categorias_count = 0
        maquinas_count = 0
        imported_categories: List[str] = []

        def normalize_cat_name(name: str) -> str:
            name = re.sub(r"[^a-zA-Z0-9 ]", "", name)
            name = name.strip().lower()
            return re.sub(r"\s+", "_", name)

        cat_cache: Dict[str, int] = {}
        in_category_section = False

        with open(catver_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip()
                    if section == "Category":
                        in_category_section = True
                        continue
                    if section == "VerAdded":
                        break
                    in_category_section = False
                    continue
                if not in_category_section or "=" not in line:
                    continue

                rom_name, cat_full = line.split("=", 1)
                rom_name = rom_name.strip()
                cat_full = cat_full.strip().replace(" * Mature *", "").strip()
                if "/" in cat_full:
                    primary = cat_full.split("/", 1)[0].strip()
                elif ":" in cat_full:
                    primary = cat_full.split(":", 1)[0].strip()
                else:
                    primary = cat_full
                if not primary:
                    continue

                cat_name = normalize_cat_name(primary)
                if cat_name in UNWANTED_CATEGORIES:
                    continue
                if cat_name not in cat_cache:
                    cursor.execute("SELECT id FROM category WHERE name = ?", (cat_name,))
                    row = cursor.fetchone()
                    if row:
                        cat_id = row[0]
                    else:
                        cursor.execute(
                            "INSERT INTO category (name, display_name, source) VALUES (?, ?, ?)",
                            (cat_name, primary, "catver.ini"),
                        )
                        cat_id = cursor.lastrowid
                        categorias_count += 1
                        imported_categories.append(primary)
                    cat_cache[cat_name] = cat_id

                cat_id = cat_cache[cat_name]
                cursor.execute("SELECT id FROM machine WHERE name = ?", (rom_name,))
                row = cursor.fetchone()
                if row:
                    machine_id = row[0]
                    cursor.execute(
                        "INSERT OR IGNORE INTO machine_category (machine_id, category_id) VALUES (?, ?)",
                        (machine_id, cat_id),
                    )
                    if cursor.rowcount > 0:
                        maquinas_count += 1

        self.conn.commit()
        return categorias_count, maquinas_count, imported_categories

    # ========================================================================
    # CONSTRUÇÃO DA CONSULTA SQL
    # ========================================================================

    def _build_filter_query(self, criteria: FilterCriteria) -> tuple[str, list]:
        """Constrói a parte SQL dos filtros que o banco consegue resolver."""
        query = "SELECT DISTINCT m.id FROM machine m"
        params: list = []
        where_clauses: list = []

        if criteria.emulation_status:
            status_list = [s for s in ("working", "imperfect", "not_working") if s in criteria.emulation_status]
            if status_list:
                placeholders = ",".join(["?"] * len(status_list))
                where_clauses.append(f"m.emulation_status IN ({placeholders})")
                params.extend(status_list)
        if not criteria.include_clones:
            where_clauses.append("(m.cloneof IS NULL OR m.cloneof = '')")
        if not criteria.include_bios:
            where_clauses.append("m.is_bios = 0")
        if not criteria.include_devices:
            where_clauses.append("m.is_device = 0")
        if not criteria.include_chd:
            where_clauses.append("NOT EXISTS (SELECT 1 FROM disk d WHERE d.machine_id = m.id)")
        if criteria.exclude_categories:
            placeholders = ",".join(["?"] * len(criteria.exclude_categories))
            where_clauses.append(
                "NOT EXISTS (SELECT 1 FROM machine_category mc JOIN category c ON c.id = mc.category_id "
                f"WHERE mc.machine_id = m.id AND c.name IN ({placeholders}))"
            )
            params.extend(criteria.exclude_categories)
        if criteria.include_categories:
            placeholders = ",".join(["?"] * len(criteria.include_categories))
            where_clauses.append(
                "EXISTS (SELECT 1 FROM machine_category mc JOIN category c ON c.id = mc.category_id "
                f"WHERE mc.machine_id = m.id AND c.name IN ({placeholders}))"
            )
            params.extend(criteria.include_categories)
        if criteria.arcade_systems:
            placeholders = ",".join(["?"] * len(criteria.arcade_systems))
            where_clauses.append(f"m.name IN ({placeholders})")
            params.extend(criteria.arcade_systems)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        return query, params

    def _apply_emulator_target(self, machine_ids: List[int], criteria: FilterCriteria) -> List[int]:
        """Aplica o perfil de emulador após os filtros SQL.

        A resolução é feita sobre os metadados armazenados no banco, sem
        reabrir o LISTXML. Isso mantém o SQL simples e evita duplicar no banco
        as regras específicas de cada emulador.
        """
        target_name = (criteria.emulator_target or "mame").strip().lower()
        if target_name in {"", "mame"}:
            return machine_ids
        try:
            target = ReconstructionTarget(target_name)
        except ValueError as exc:
            raise ValueError(f"Destino de emulador inválido: {target_name}") from exc

        if not machine_ids:
            return []

        placeholders = ",".join("?" for _ in machine_ids)
        rows = self.conn.execute(
            f"SELECT id, name, description, sourcefile, is_bios, is_device FROM machine WHERE id IN ({placeholders})",
            machine_ids,
        ).fetchall()

        accepted: set[int] = set()
        for row in rows:
            machine = ET.Element("machine", {
                "name": row[1] or "",
                "sourcefile": row[3] or "",
                "isbios": "yes" if row[4] else "no",
                "isdevice": "yes" if row[5] else "no",
            })
            ET.SubElement(machine, "description").text = row[2] or ""
            resolution = self.platform_resolver.resolve(machine)
            if resolution.supported and resolution.target is target:
                accepted.add(row[0])

        return [machine_id for machine_id in machine_ids if machine_id in accepted]

    def _get_filtered_machine_ids(self, criteria: FilterCriteria) -> List[int]:
        """Retorna os IDs finais após SQL + resolução de plataforma."""
        query, params = self._build_filter_query(criteria)
        ids = [row[0] for row in self.conn.execute(query, params).fetchall()]
        return self._apply_emulator_target(ids, criteria)

    # ========================================================================
    # MÉTODOS PÚBLICOS
    # ========================================================================

    def apply_filters(self, criteria: FilterCriteria) -> List[int]:
        return self._get_filtered_machine_ids(criteria)

    def get_machine_names(self, criteria: FilterCriteria) -> List[str]:
        """Retorna os nomes das machines após todos os filtros."""
        ids = self._get_filtered_machine_ids(criteria)
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self.conn.execute(
            f"SELECT name FROM machine WHERE id IN ({placeholders}) ORDER BY name", ids
        ).fetchall()
        return [row[0] for row in rows]

    def get_machine_count(self, criteria: FilterCriteria) -> int:
        return len(self._get_filtered_machine_ids(criteria))

    def get_rom_count(self, criteria: FilterCriteria) -> int:
        ids = self._get_filtered_machine_ids(criteria)
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        return self.conn.execute(
            f"SELECT COUNT(*) FROM rom WHERE machine_id IN ({placeholders})", ids
        ).fetchone()[0]

    def get_chd_count(self, criteria: FilterCriteria) -> int:
        ids = self._get_filtered_machine_ids(criteria)
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        return self.conn.execute(
            f"SELECT COUNT(*) FROM disk WHERE machine_id IN ({placeholders})", ids
        ).fetchone()[0]

    def get_estimated_size(self, criteria: FilterCriteria) -> int:
        ids = self._get_filtered_machine_ids(criteria)
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        rom_size = self.conn.execute(
            f"SELECT COALESCE(SUM(size), 0) FROM rom WHERE machine_id IN ({placeholders})", ids
        ).fetchone()[0]
        chd_size = self.conn.execute(
            f"SELECT COALESCE(SUM(size), 0) FROM disk WHERE machine_id IN ({placeholders})", ids
        ).fetchone()[0]
        return rom_size + chd_size

    def get_unscanned_chd_count(self, criteria: FilterCriteria) -> int:
        ids = self._get_filtered_machine_ids(criteria)
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        return self.conn.execute(
            f"SELECT COUNT(*) FROM disk WHERE (size IS NULL OR size = 0) AND machine_id IN ({placeholders})",
            ids,
        ).fetchone()[0]

    # ========================================================================
    # PERFIS
    # ========================================================================

    def get_profiles(self) -> List[FilterProfile]:
        return self.profile_repo.get_all()

    def save_profile(self, profile: FilterProfile) -> int:
        return self.profile_repo.save(profile)

    def delete_profile(self, profile_id: int) -> None:
        self.profile_repo.delete(profile_id)

    def set_default_profile(self, profile_id: int) -> None:
        self.profile_repo.set_default(profile_id)

    def get_default_profile(self) -> Optional[FilterProfile]:
        return self.profile_repo.get_default()

    def seed_default_categories(self) -> None:
        from app.core.models.category import Category
        default_categories = [
            ("arcade", "Arcade"), ("system", "System"), ("electromechanical", "Electromechanical"),
            ("casino", "Casino"), ("driving", "Driving"), ("fighter", "Fighter"), ("gambling", "Gambling"),
            ("game_console", "Game Console"), ("ball_paddle", "Ball & Paddle"), ("board_game", "Board Game"),
            ("calculator", "Calculator"), ("card_games", "Card Games"), ("maze", "Maze"),
            ("handheld", "Handheld"), ("climbing", "Climbing"), ("medal_game", "Medal Game"),
            ("platform", "Platform"), ("shooter", "Shooter"), ("slot_machine", "Slot Machine"),
            ("sports", "Sports"), ("tabletop", "Tabletop"), ("telephone", "Telephone"),
            ("multigame", "MultiGame"), ("music_player", "Music Player"), ("computer", "Computer"),
            ("multiplay", "Multiplay"), ("puzzle", "Puzzle"), ("misc", "Misc."), ("utilities", "Utilities"),
            ("quiz", "Quiz"), ("musical_instrument_accessory", "Musical Instrument Accessory"),
            ("redemption_game", "Redemption Game"), ("musical_instrument", "Musical Instrument"),
            ("robot", "Robot"), ("whacamole", "Whac-A-Mole"), ("ttl_shooter", "TTL * Shooter"),
            ("road_indicator", "Road Indicator"), ("music_game", "Music Game"), ("ttl_sports", "TTL * Sports"),
            ("ttl_ball_paddle", "TTL * Ball & Paddle"), ("radio", "Radio"),
            ("medical_equipment", "Medical Equipment"), ("bartop", "Bartop"),
            ("ttl_driving", "TTL * Driving"), ("digital_simulator", "Digital Simulator"),
            ("printer", "Printer"), ("tv_bundle", "TV Bundle"), ("simulation", "Simulation"),
            ("computer_graphic_workstation", "Computer Graphic Workstation"), ("non_arcade", "Non Arcade"),
            ("tablet", "Tablet"), ("digital_camera", "Digital Camera"), ("player", "Player"),
            ("watch", "Watch"), ("touchscreen", "Touchscreen"), ("ttl_maze", "TTL * Maze"),
            ("ttl_quiz", "TTL * Quiz"),
        ]
        for name, display in default_categories:
            self.category_repo.insert(Category(name=name, display_name=display, source="manual"))
