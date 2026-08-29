"""Repositório para categorias."""
import sqlite3

from app.core.models.category import Category


class CategoryRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_all(self) -> list[Category]:
        cursor = self.conn.execute("SELECT id, name, display_name, source FROM category ORDER BY display_name")
        rows = cursor.fetchall()
        return [Category(id=row[0], name=row[1], display_name=row[2], source=row[3]) for row in rows]

    def get_by_name(self, name: str) -> Category | None:
        cursor = self.conn.execute("SELECT id, name, display_name, source FROM category WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return Category(id=row[0], name=row[1], display_name=row[2], source=row[3])
        return None

    def get_by_id(self, category_id: int) -> Category | None:
        cursor = self.conn.execute("SELECT id, name, display_name, source FROM category WHERE id = ?", (category_id,))
        row = cursor.fetchone()
        if row:
            return Category(id=row[0], name=row[1], display_name=row[2], source=row[3])
        return None

    def insert(self, category: Category) -> int:
        cursor = self.conn.execute(
            "INSERT OR IGNORE INTO category (name, display_name, source) VALUES (?, ?, ?)",
            (category.name, category.display_name, category.source)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_machine_categories(self, machine_id: int) -> list[str]:
        cursor = self.conn.execute(
            """SELECT c.name FROM category c
               JOIN machine_category mc ON mc.category_id = c.id
               WHERE mc.machine_id = ?""",
            (machine_id,)
        )
        return [row[0] for row in cursor.fetchall()]

    def assign_category_to_machine(self, machine_id: int, category_id: int) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO machine_category (machine_id, category_id) VALUES (?, ?)",
            (machine_id, category_id)
        )
        self.conn.commit()

    def assign_categories_to_machine(self, machine_id: int, category_names: list[str]) -> None:
        for name in category_names:
            cat = self.get_by_name(name)
            if cat:
                self.assign_category_to_machine(machine_id, cat.id)