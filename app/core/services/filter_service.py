"""Serviço central para filtragem de máquinas."""
import sqlite3
from typing import List, Optional, Set, Dict, Any
from app.core.models.filter_profile import FilterCriteria, FilterProfile
from app.database.repositories.category_repository import CategoryRepository
from app.database.repositories.filter_profile_repository import FilterProfileRepository

class FilterService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.category_repo = CategoryRepository(conn)
        self.profile_repo = FilterProfileRepository(conn)

    def get_categories(self) -> List[str]:
        """Retorna lista de nomes de categorias disponíveis."""
        return [cat.name for cat in self.category_repo.get_all()]

    def get_category_display_names(self) -> Dict[str, str]:
        """Retorna mapeamento nome -> nome exibido."""
        return {cat.name: cat.display_name for cat in self.category_repo.get_all()}

    def apply_filters(self, criteria: FilterCriteria) -> List[int]:
        """
        Aplica os filtros e retorna uma lista de machine_ids.
        """
        query = "SELECT DISTINCT m.id FROM machine m"
        params = []
        where_clauses = []

        # Filtro por categoria (se houver)
        if criteria.categories:
            placeholders = ",".join(["?"] * len(criteria.categories))
            query += """
                JOIN machine_category mc ON mc.machine_id = m.id
                JOIN category c ON c.id = mc.category_id
            """
            where_clauses.append(f"c.name IN ({placeholders})")
            params.extend(criteria.categories)

        # Filtro por estado de emulação (cumulativo)
        status_map = {
            "working": "working",
            "imperfect": "imperfect",
            "not_working": "not_working"
        }
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

        # Incluir clones
        if not criteria.include_clones:
            where_clauses.append("(m.cloneof IS NULL OR m.cloneof = '')")

        # Incluir BIOS
        if not criteria.include_bios:
            where_clauses.append("m.is_bios = 0")

        # Incluir devices
        if not criteria.include_devices:
            where_clauses.append("m.is_device = 0")

        # Incluir CHD (baseado na existência de discos)
        if criteria.include_chd:
            # Se `include_chd` for True, não filtra por CHD (mantém todos)
            pass
        else:
            # Excluir máquinas que têm CHD (disks)
            query += " LEFT JOIN disk d ON d.machine_id = m.id"
            where_clauses.append("d.id IS NULL")

        # Arcade systems (lista de sistemas considerados arcade)
        if criteria.arcade_systems:
            placeholders = ",".join(["?"] * len(criteria.arcade_systems))
            where_clauses.append(f"m.name IN ({placeholders})")
            params.extend(criteria.arcade_systems)

        # Monta query final
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        cursor = self.conn.execute(query, params)
        return [row[0] for row in cursor.fetchall()]

    def get_profiles(self) -> List[FilterProfile]:
        """Retorna todos os perfis salvos."""
        return self.profile_repo.get_all()

    def save_profile(self, profile: FilterProfile) -> int:
        """Salva ou atualiza um perfil."""
        return self.profile_repo.save(profile)

    def delete_profile(self, profile_id: int) -> None:
        """Remove um perfil."""
        self.profile_repo.delete(profile_id)

    def set_default_profile(self, profile_id: int) -> None:
        """Define um perfil como padrão."""
        self.profile_repo.set_default(profile_id)

    def get_default_profile(self) -> Optional[FilterProfile]:
        """Retorna o perfil padrão."""
        return self.profile_repo.get_default()

    def get_machine_count(self, criteria: FilterCriteria) -> int:
        """Retorna o número de máquinas que atendem aos critérios."""
        machine_ids = self.apply_filters(criteria)
        return len(machine_ids)

    def get_rom_count(self, criteria: FilterCriteria) -> int:
        """Retorna o número total de ROMs das máquinas filtradas."""
        machine_ids = self.apply_filters(criteria)
        if not machine_ids:
            return 0
        placeholders = ",".join(["?"] * len(machine_ids))
        query = f"SELECT COUNT(*) FROM rom r WHERE r.machine_id IN ({placeholders})"
        cursor = self.conn.execute(query, machine_ids)
        result = cursor.fetchone()
        return result[0] if result else 0

    def get_estimated_size(self, criteria: FilterCriteria) -> int:
        """
        Estima o tamanho total (em bytes) das ROMs das máquinas filtradas.
        Aproximação: soma dos tamanhos das ROMs (sem considerar CHDs).
        """
        machine_ids = self.apply_filters(criteria)
        if not machine_ids:
            return 0
        placeholders = ",".join(["?"] * len(machine_ids))
        query = f"SELECT SUM(r.size) FROM rom r WHERE r.machine_id IN ({placeholders})"
        cursor = self.conn.execute(query, machine_ids)
        result = cursor.fetchone()
        return result[0] if result and result[0] else 0