"""
Motor de filtros – constrói consulta SQL a partir do perfil e retorna máquinas selecionadas.
"""

import sqlite3
import logging
from typing import List, Dict, Any, Optional
from ..domain.set_profile import SetProfile
from .predicates import build_conditions

logger = logging.getLogger(__name__)

class FilterEngine:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def apply(self, profile: SetProfile) -> List[Dict[str, Any]]:
        """
        Aplica os filtros do perfil e retorna lista de máquinas selecionadas.
        """
        conditions = build_conditions(profile)
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
        SELECT 
            m.id,
            m.name,
            m.description,
            m.year,
            m.manufacturer,
            m.cloneof,
            m.isbios,
            m.isdevice,
            m.ismechanical,
            m.runnable,
            mc.category,
            d.emulation,
            d.status
        FROM machine m
        LEFT JOIN machine_classification mc ON m.id = mc.machine_id
        LEFT JOIN driver d ON m.id = d.machine_id
        WHERE {where_clause}
        ORDER BY m.name
        """
        
        cursor = self.conn.execute(query)
        results = [dict(row) for row in cursor]
        logger.info(f"Filtro aplicado: {len(results)} máquinas selecionadas.")
        return results

    def count(self, profile: SetProfile) -> int:
        """Retorna o número de máquinas que atendem aos filtros (sem carregar todos os dados)."""
        conditions = build_conditions(profile)
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
        SELECT COUNT(*) as total
        FROM machine m
        LEFT JOIN machine_classification mc ON m.id = mc.machine_id
        LEFT JOIN driver d ON m.id = d.machine_id
        WHERE {where_clause}
        """
        
        cursor = self.conn.execute(query)
        row = cursor.fetchone()
        return row["total"] if row else 0