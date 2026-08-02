import sqlite3

from pathlib import Path

from core.schema import SCHEMA


class Database:

    def __init__(self, dbfile: Path):

        self.conn = sqlite3.connect(dbfile)

        self.conn.execute("PRAGMA foreign_keys=ON")

        self.conn.executescript(SCHEMA)

    def cursor(self):

        return self.conn.cursor()

    def commit(self):

        self.conn.commit()

    def close(self):

        self.conn.close()