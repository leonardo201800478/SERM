from ..connection import Database

class DatasetRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, version: str, executable_path: str) -> int:
        conn = self.db.connect()
        cur = conn.execute(
            "INSERT INTO dataset (version, source_executable) VALUES (?, ?)",
            (version, executable_path)
        )
        conn.commit()
        return cur.lastrowid

    def get_by_version(self, version: str) -> dict | None:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT * FROM dataset WHERE version = ?", (version,)
        ).fetchone()
        return dict(row) if row else None