"""Serviço central para filtragem de máquinas e importação de categorias."""
import sqlite3
import logging
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from app.core.models.filter_profile import FilterCriteria, FilterProfile
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
        """Retorna lista de nomes de categorias disponíveis."""
        return [cat.name for cat in self.category_repo.get_all()]

    def get_category_display_names(self) -> Dict[str, str]:
        """Retorna mapeamento nome -> nome exibido."""
        return {cat.name: cat.display_name for cat in self.category_repo.get_all()}

    def get_categories_with_counts(self) -> List[Dict[str, Any]]:
        """Retorna lista de categorias com contagem de máquinas associadas."""
        cursor = self.conn.execute("""
            SELECT c.name, c.display_name, COUNT(mc.machine_id) as count
            FROM category c
            LEFT JOIN machine_category mc ON mc.category_id = c.id
            GROUP BY c.id
            ORDER BY c.display_name
        """)
        rows = cursor.fetchall()
        return [{"name": row[0], "display_name": row[1], "count": row[2]} for row in rows]

    def import_categories_from_ini(self, ini_path: Path) -> Tuple[int, int, List[str]]:
        """
        Importa categorias e associações do arquivo category.ini do MAME.
        Retorna (categorias_importadas, maquinas_associadas, lista_de_categorias_importadas).
        """
        if not ini_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {ini_path}")

        cursor = self.conn.cursor()
        categorias_count = 0
        maquinas_count = 0
        imported_categories = []

        categoria_cache = {}

        def normalize_cat_name(name: str) -> str:
            name = re.sub(r'[^a-zA-Z0-9 ]', '', name)
            name = name.strip().lower()
            name = re.sub(r'\s+', '_', name)
            return name

        current_section = None

        with open(ini_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if line.startswith('[') and line.endswith(']'):
                    section = line[1:-1].strip()
                    if section == 'FOLDER_SETTINGS':
                        current_section = None
                        continue

                    cat_name = normalize_cat_name(section)
                    display_name = section

                    cursor.execute("SELECT id FROM category WHERE name = ?", (cat_name,))
                    row = cursor.fetchone()
                    if row:
                        cat_id = row[0]
                    else:
                        cursor.execute(
                            "INSERT INTO category (name, display_name, source) VALUES (?, ?, ?)",
                            (cat_name, display_name, 'category.ini')
                        )
                        cat_id = cursor.lastrowid
                        categorias_count += 1
                        imported_categories.append(display_name)
                        self.conn.commit()

                    categoria_cache[section] = cat_id
                    current_section = section
                    continue

                if current_section is None:
                    continue

                machine_name = line.strip()
                if not machine_name:
                    continue

                cat_id = categoria_cache.get(current_section)
                if cat_id is None:
                    continue

                cursor.execute("SELECT id FROM machine WHERE name = ?", (machine_name,))
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

    # Seções que não representam categorias de máquinas no catlist.ini.
    _CATLIST_IGNORED_SECTIONS = frozenset({'FOLDER_SETTINGS', 'ROOT_FOLDER'})

    @staticmethod
    def _catlist_primary_category(section: str) -> str:
        """Extrai o "primeiro filtro" de um cabeçalho do catlist.ini.

        Regras observadas no arquivo real do catlist.ini (progetto-snaps):
        - Seções de Arcade usam ':' como separador do nível principal, ex.:
          "[Arcade: Driving / Race (chase view)]" -> "Arcade".
        - Todas as demais usam '/', ex.:
          "[Tablet / Multi-Functional for Children]" -> "Tablet".
        - Seções sem nenhum separador são usadas como estão (ex.: "System").
        """
        section = section.strip()
        if ':' in section:
            return section.split(':', 1)[0].strip()
        if '/' in section:
            return section.split('/', 1)[0].strip()
        return section

    def import_categories_from_catlist(self, catlist_path: Path) -> Tuple[int, int, List[str]]:
        """
        Importa categorias a partir do catlist.ini (progetto-snaps), agrupando
        por apenas o PRIMEIRO nível do cabeçalho de cada seção — ex.:
        "[Arcade: Driving / Race (chase view)]" vira apenas a categoria
        "Arcade", e "[Tablet / Multi-Functional for Children]" vira apenas
        "Tablet". Isso evita a explosão de ~680 subcategorias (uma por seção)
        e mantém o filtro da GUI em poucas opções realmente úteis.

        Retorna (categorias_importadas, maquinas_associadas, lista_de_categorias_importadas).
        """
        if not catlist_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {catlist_path}")

        cursor = self.conn.cursor()
        categorias_count = 0
        maquinas_count = 0
        imported_categories = []

        def normalize_cat_name(name: str) -> str:
            name = re.sub(r'[^a-zA-Z0-9 ]', '', name)
            name = name.strip().lower()
            name = re.sub(r'\s+', '_', name)
            return name

        # cat_name normalizado -> id no banco (agrega todas as subseções que
        # mapeiam para a mesma categoria principal, ex.: as ~383 seções
        # "Arcade: ..." todas caem no mesmo cat_id de "arcade").
        categoria_cache: Dict[str, int] = {}
        current_cat_id = None

        with open(catlist_path, 'r', encoding='utf-8', errors='ignore') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith(';'):
                    continue

                if line.startswith('[') and line.endswith(']'):
                    section = line[1:-1].strip()
                    if section in self._CATLIST_IGNORED_SECTIONS or not section:
                        current_cat_id = None
                        continue

                    primary = self._catlist_primary_category(section)
                    cat_name = normalize_cat_name(primary)
                    if not cat_name:
                        current_cat_id = None
                        continue

                    if cat_name in categoria_cache:
                        current_cat_id = categoria_cache[cat_name]
                        continue

                    cursor.execute("SELECT id FROM category WHERE name = ?", (cat_name,))
                    row = cursor.fetchone()
                    if row:
                        cat_id = row[0]
                    else:
                        cursor.execute(
                            "INSERT INTO category (name, display_name, source) VALUES (?, ?, ?)",
                            (cat_name, primary, 'catlist.ini')
                        )
                        cat_id = cursor.lastrowid
                        categorias_count += 1
                        imported_categories.append(primary)

                    categoria_cache[cat_name] = cat_id
                    current_cat_id = cat_id
                    continue

                if current_cat_id is None:
                    continue

                machine_name = line
                cursor.execute("SELECT id FROM machine WHERE name = ?", (machine_name,))
                row = cursor.fetchone()
                if row:
                    machine_id = row[0]
                    cursor.execute(
                        "INSERT OR IGNORE INTO machine_category (machine_id, category_id) VALUES (?, ?)",
                        (machine_id, current_cat_id)
                    )
                    if cursor.rowcount > 0:
                        maquinas_count += 1

        self.conn.commit()
        return categorias_count, maquinas_count, imported_categories

    # ========================================================================
    # CONSTRUÇÃO DA CONSULTA SQL
    # ========================================================================

    def _build_filter_query(self, criteria: FilterCriteria) -> tuple[str, list]:
        query = "SELECT DISTINCT m.id FROM machine m"
        params = []
        where_clauses = []

        # 1. Estado de emulação
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

        # 3. CHD (exclui máquinas que têm discos)
        if not criteria.include_chd:
            where_clauses.append("NOT EXISTS (SELECT 1 FROM disk d WHERE d.machine_id = m.id)")

        # 4. Categorias
        if criteria.categories:
            query += """
                INNER JOIN machine_category mc ON mc.machine_id = m.id
                INNER JOIN category c ON c.id = mc.category_id
            """
            placeholders = ",".join(["?"] * len(criteria.categories))
            where_clauses.append(f"c.name IN ({placeholders})")
            params.extend(criteria.categories)

        # 5. Arcade Systems
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
        """Soma o tamanho estimado (ROMs + CHDs) das máquinas filtradas.

        O tamanho de ROMs vem direto do -listxml. O tamanho de CHDs só é
        conhecido depois de rodar o scanner (ver
        ``DatabaseService.update_chd_sizes`` / ``app.mame.chd_scanner``),
        que lê os arquivos .chd reais no rompath configurado — o listxml
        não informa esse dado. Enquanto o scanner não roda, `disk.size`
        fica em 0 e essas máquinas ainda entram na contagem de máquinas/CHDs,
        mas não somam bytes aqui (ver ``get_unscanned_chd_count`` para saber
        se isso está subestimando o total).
        """
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
        """Quantos CHDs, dentre as máquinas filtradas, ainda não têm tamanho lido.

        Use para avisar na UI que o "Tamanho estimado" pode estar
        subestimado até rodar o scanner de CHD.
        """
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
        default_categories = [
            ("arcade", "Arcade"),
            ("system", "System"),
            ("bios", "BIOS"),
            ("devices", "Devices"),
            ("electromechanical", "Electromechanical"),
            ("casino", "Casino"),
            ("mahjong", "Mahjong"),
            ("screenless", "Screenless"),
            ("mature", "Mature"),
            ("driving", "Driving"),
            ("fighter", "Fighter"),
            ("gambling", "Gambling"),
            ("game_console", "Game Console"),
            ("chd", "CHD"),
            ("ball_paddle", "Ball & Paddle"),
            ("board_game", "Board Game"),
            ("calculator", "Calculator"),
            ("card_games", "Card Games"),
            ("maze", "Maze"),
            ("handheld", "Handheld"),
            ("climbing", "Climbing"),
            ("medal_game", "Medal Game"),
            ("musical", "Musical"),
            ("platform", "Platform"),
            ("shooter", "Shooter"),
            ("slot_machine", "Slot Machine"),
            ("sports", "Sports"),
            ("tabletop", "Tabletop"),
            ("telephone", "Telephone"),
        ]
        for name, display in default_categories:
            cat = Category(name=name, display_name=display, source="manual")
            self.category_repo.insert(cat)