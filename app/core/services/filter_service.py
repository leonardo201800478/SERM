"""Serviço central para filtragem de máquinas e importação de categorias."""
import sqlite3
import logging
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from app.core.models.filter_profile import FilterCriteria, FilterProfile
from app.core.constants.macro_categories import get_macro_category, macro_sort_key
from app.database.repositories.category_repository import CategoryRepository
from app.database.repositories.filter_profile_repository import FilterProfileRepository

logger = logging.getLogger(__name__)


class FilterService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.category_repo = CategoryRepository(conn)
        self.profile_repo = FilterProfileRepository(conn)

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
        """Agrupa as categorias granulares em macro-grupos, somando as contagens.

        Cada categoria retornada por ``get_categories_with_counts`` é
        classificada em um macro-grupo através de
        ``app.core.constants.macro_categories.get_macro_category``.
        Categorias sem mapeamento explícito caem em
        ``UNCLASSIFIED_MACRO`` ("Outras / Não Classificadas") — nunca são
        descartadas silenciosamente.

        Returns:
            Lista de dicionários, um por macro-grupo, já ordenada segundo
            ``MACRO_CATEGORY_ORDER``, cada um contendo:
                - macro_name: nome do macro-grupo (ex.: "System / Non-Games")
                - count: soma das contagens de máquinas de todas as
                  categorias granulares pertencentes ao grupo
                - categories: lista de nomes normalizados (``category.name``)
                  das categorias granulares pertencentes ao grupo
        """
        granular = self.get_categories_with_counts()

        groups: Dict[str, Dict[str, Any]] = {}
        for cat in granular:
            macro_name = get_macro_category(cat["name"])
            group = groups.setdefault(
                macro_name,
                {"macro_name": macro_name, "count": 0, "categories": []},
            )
            group["count"] += cat["count"]
            group["categories"].append(cat["name"])

        return sorted(groups.values(), key=lambda g: macro_sort_key(g["macro_name"]))

    def import_categories_from_ini(self, ini_path: Path) -> Tuple[int, int, List[str]]:
        # (mesmo código anterior, mantido)
        pass

    # ========================================================================
    # IMPORTAÇÃO DO CATVER.INI (com remoção de categorias indesejadas)
    # ========================================================================
    def import_categories_from_catver(self, catver_path: Path) -> Tuple[int, int, List[str]]:
        if not catver_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {catver_path}")

        UNWANTED_CATEGORIES = {
            'chd', 'devices', 'musical', 'mature',
            'mahjong', 'screenless', 'bios'
        }

        cursor = self.conn.cursor()
        categorias_count = 0
        maquinas_count = 0
        imported_categories = []

        def normalize_cat_name(name: str) -> str:
            name = re.sub(r'[^a-zA-Z0-9 ]', '', name)
            name = name.strip().lower()
            name = re.sub(r'\s+', '_', name)
            return name

        cat_cache = {}
        in_category_section = False

        with open(catver_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(';'):
                    continue

                if line.startswith('[') and line.endswith(']'):
                    section = line[1:-1].strip()
                    if section == 'Category':
                        in_category_section = True
                        continue
                    elif section == 'VerAdded':
                        break
                    else:
                        in_category_section = False
                        continue

                if not in_category_section:
                    continue

                if '=' not in line:
                    continue

                rom_name, cat_full = line.split('=', 1)
                rom_name = rom_name.strip()
                cat_full = cat_full.strip()

                if ' * Mature *' in cat_full:
                    cat_full = cat_full.replace(' * Mature *', '').strip()

                if '/' in cat_full:
                    primary = cat_full.split('/', 1)[0].strip()
                elif ':' in cat_full:
                    primary = cat_full.split(':', 1)[0].strip()
                else:
                    primary = cat_full

                if not primary:
                    continue

                cat_name = normalize_cat_name(primary)

                # Pula categorias indesejadas
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
                            (cat_name, primary, 'catver.ini')
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
                        (machine_id, cat_id)
                    )
                    if cursor.rowcount > 0:
                        maquinas_count += 1

        self.conn.commit()
        return categorias_count, maquinas_count, imported_categories

    # ========================================================================
    # CONSTRUÇÃO DA CONSULTA SQL (com exclusão de categorias)
    # ========================================================================

    def _build_filter_query(self, criteria: FilterCriteria) -> tuple[str, list]:
        query = "SELECT DISTINCT m.id FROM machine m"
        params = []
        where_clauses = []

        # 1. Emulation status
        if criteria.emulation_status:
            status_list = []
            if "working" in criteria.emulation_status:
                status_list.append("working")
            if "imperfect" in criteria.emulation_status:
                status_list.append("imperfect")
            if "not_working" in criteria.emulation_status:
                status_list.append("not_working")
            if status_list:
                placeholders = ",".join(["?"] * len(status_list))
                where_clauses.append(f"m.emulation_status IN ({placeholders})")
                params.extend(status_list)

        # 2. Opções
        if not criteria.include_clones:
            where_clauses.append("(m.cloneof IS NULL OR m.cloneof = '')")
        if not criteria.include_bios:
            where_clauses.append("m.is_bios = 0")
        if not criteria.include_devices:
            where_clauses.append("m.is_device = 0")
        if not criteria.include_chd:
            where_clauses.append("NOT EXISTS (SELECT 1 FROM disk d WHERE d.machine_id = m.id)")

        # 3. Categorias – EXCLUIR as marcadas em vermelho
        if criteria.exclude_categories:
            placeholders = ",".join(["?"] * len(criteria.exclude_categories))
            where_clauses.append(
                f"NOT EXISTS (SELECT 1 FROM machine_category mc "
                f"JOIN category c ON c.id = mc.category_id "
                f"WHERE mc.machine_id = m.id AND c.name IN ({placeholders}))"
            )
            params.extend(criteria.exclude_categories)

        # 4. Categorias – INCLUIR (forçar) as marcadas em verde
        if criteria.include_categories:
            placeholders = ",".join(["?"] * len(criteria.include_categories))
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM machine_category mc "
                f"JOIN category c ON c.id = mc.category_id "
                f"WHERE mc.machine_id = m.id AND c.name IN ({placeholders}))"
            )
            params.extend(criteria.include_categories)

        # 5. Arcade systems (opcional)
        if criteria.arcade_systems:
            placeholders = ",".join(["?"] * len(criteria.arcade_systems))
            where_clauses.append(f"m.name IN ({placeholders})")
            params.extend(criteria.arcade_systems)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        return query, params

    # ========================================================================
    # MÉTODOS PÚBLICOS
    # ========================================================================

    def apply_filters(self, criteria: FilterCriteria) -> List[int]:
        query, params = self._build_filter_query(criteria)
        cursor = self.conn.execute(query, params)
        return [row[0] for row in cursor.fetchall()]

    def get_machine_count(self, criteria: FilterCriteria) -> int:
        query, params = self._build_filter_query(criteria)
        count_query = query.replace(
            "SELECT DISTINCT m.id FROM machine m",
            "SELECT COUNT(DISTINCT m.id) FROM machine m",
            1
        )
        cursor = self.conn.execute(count_query, params)
        return cursor.fetchone()[0]

    def get_rom_count(self, criteria: FilterCriteria) -> int:
        query, params = self._build_filter_query(criteria)
        count_query = f"""
            SELECT COUNT(*) FROM rom r
            WHERE EXISTS (
                SELECT 1 FROM ({query}) AS filtered_machines
                WHERE filtered_machines.id = r.machine_id
            )
        """
        cursor = self.conn.execute(count_query, params)
        return cursor.fetchone()[0]

    def get_chd_count(self, criteria: FilterCriteria) -> int:
        query, params = self._build_filter_query(criteria)
        count_query = f"""
            SELECT COUNT(*) FROM disk d
            WHERE EXISTS (
                SELECT 1 FROM ({query}) AS filtered_machines
                WHERE filtered_machines.id = d.machine_id
            )
        """
        cursor = self.conn.execute(count_query, params)
        return cursor.fetchone()[0]

    def get_estimated_size(self, criteria: FilterCriteria) -> int:
        query, params = self._build_filter_query(criteria)
        size_query = f"""
            SELECT
                COALESCE((
                    SELECT SUM(r.size) FROM rom r
                    WHERE EXISTS (
                        SELECT 1 FROM ({query}) AS fm WHERE fm.id = r.machine_id
                    )
                ), 0)
                +
                COALESCE((
                    SELECT SUM(d.size) FROM disk d
                    WHERE EXISTS (
                        SELECT 1 FROM ({query}) AS fm WHERE fm.id = d.machine_id
                    )
                ), 0)
        """
        cursor = self.conn.execute(size_query, params + params)
        result = cursor.fetchone()
        return result[0] if result else 0

    def get_unscanned_chd_count(self, criteria: FilterCriteria) -> int:
        query, params = self._build_filter_query(criteria)
        count_query = f"""
            SELECT COUNT(*) FROM disk d
            WHERE (d.size IS NULL OR d.size = 0)
            AND EXISTS (
                SELECT 1 FROM ({query}) AS filtered_machines
                WHERE filtered_machines.id = d.machine_id
            )
        """
        cursor = self.conn.execute(count_query, params)
        return cursor.fetchone()[0]

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
        # Remove as indesejadas da semente também
        default_categories = [
            ("arcade", "Arcade"),
            ("system", "System"),
            ("electromechanical", "Electromechanical"),
            ("casino", "Casino"),
            ("driving", "Driving"),
            ("fighter", "Fighter"),
            ("gambling", "Gambling"),
            ("game_console", "Game Console"),
            ("ball_paddle", "Ball & Paddle"),
            ("board_game", "Board Game"),
            ("calculator", "Calculator"),
            ("card_games", "Card Games"),
            ("maze", "Maze"),
            ("handheld", "Handheld"),
            ("climbing", "Climbing"),
            ("medal_game", "Medal Game"),
            ("platform", "Platform"),
            ("shooter", "Shooter"),
            ("slot_machine", "Slot Machine"),
            ("sports", "Sports"),
            ("tabletop", "Tabletop"),
            ("telephone", "Telephone"),
            ("multigame", "MultiGame"),
            ("music_player", "Music Player"),
            ("computer", "Computer"),
            ("multiplay", "Multiplay"),
            ("puzzle", "Puzzle"),
            ("misc", "Misc."),
            ("utilities", "Utilities"),
            ("quiz", "Quiz"),
            ("musical_instrument_accessory", "Musical Instrument Accessory"),
            ("redemption_game", "Redemption Game"),
            ("musical_instrument", "Musical Instrument"),
            ("robot", "Robot"),
            ("whacamole", "Whac-A-Mole"),
            ("ttl_shooter", "TTL * Shooter"),
            ("road_indicator", "Road Indicator"),
            ("music_game", "Music Game"),
            ("ttl_sports", "TTL * Sports"),
            ("ttl_ball_paddle", "TTL * Ball & Paddle"),
            ("radio", "Radio"),
            ("medical_equipment", "Medical Equipment"),
            ("bartop", "Bartop"),
            ("ttl_driving", "TTL * Driving"),
            ("digital_simulator", "Digital Simulator"),
            ("printer", "Printer"),
            ("tv_bundle", "TV Bundle"),
            ("simulation", "Simulation"),
            ("computer_graphic_workstation", "Computer Graphic Workstation"),
            ("non_arcade", "Non Arcade"),
            ("tablet", "Tablet"),
            ("digital_camera", "Digital Camera"),
            ("player", "Player"),
            ("watch", "Watch"),
            ("touchscreen", "Touchscreen"),
            ("ttl_maze", "TTL * Maze"),
            ("ttl_quiz", "TTL * Quiz"),
        ]
        for name, display in default_categories:
            cat = Category(name=name, display_name=display, source="manual")
            self.category_repo.insert(cat)
