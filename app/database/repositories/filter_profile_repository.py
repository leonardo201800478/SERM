"""Repositório para perfis de filtro."""
import json
import sqlite3
from typing import List, Optional
from app.core.models.filter_profile import FilterProfile, FilterCriteria

class FilterProfileRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_all(self) -> List[FilterProfile]:
        cursor = self.conn.execute(
            "SELECT id, name, description, profile_data, created_at, updated_at, is_default FROM filter_profile"
        )
        rows = cursor.fetchall()
        profiles = []
        for row in rows:
            data = json.loads(row[3])
            criteria = FilterCriteria.from_dict(data)
            profile = FilterProfile(
                id=row[0],
                name=row[1],
                description=row[2],
                criteria=criteria,
                created_at=row[4],
                updated_at=row[5],
                is_default=bool(row[6])
            )
            profiles.append(profile)
        return profiles

    def get_default(self) -> Optional[FilterProfile]:
        cursor = self.conn.execute(
            "SELECT id, name, description, profile_data, created_at, updated_at, is_default FROM filter_profile WHERE is_default = 1 LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            data = json.loads(row[3])
            criteria = FilterCriteria.from_dict(data)
            return FilterProfile(
                id=row[0],
                name=row[1],
                description=row[2],
                criteria=criteria,
                created_at=row[4],
                updated_at=row[5],
                is_default=True
            )
        return None

    def save(self, profile: FilterProfile) -> int:
        if profile.id:
            self.conn.execute(
                """UPDATE filter_profile
                   SET name = ?, description = ?, profile_data = ?, updated_at = CURRENT_TIMESTAMP, is_default = ?
                   WHERE id = ?""",
                (profile.name, profile.description, json.dumps(profile.criteria.to_dict()),
                 1 if profile.is_default else 0, profile.id)
            )
        else:
            cursor = self.conn.execute(
                """INSERT INTO filter_profile (name, description, profile_data, is_default)
                   VALUES (?, ?, ?, ?)""",
                (profile.name, profile.description, json.dumps(profile.criteria.to_dict()),
                 1 if profile.is_default else 0)
            )
            profile.id = cursor.lastrowid
        self.conn.commit()
        return profile.id

    def delete(self, profile_id: int) -> None:
        self.conn.execute("DELETE FROM filter_profile WHERE id = ?", (profile_id,))
        self.conn.commit()

    def set_default(self, profile_id: int) -> None:
        self.conn.execute("UPDATE filter_profile SET is_default = 0 WHERE is_default = 1")
        self.conn.execute("UPDATE filter_profile SET is_default = 1 WHERE id = ?", (profile_id,))
        self.conn.commit()