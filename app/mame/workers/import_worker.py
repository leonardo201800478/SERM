from PySide6.QtCore import QThread, Signal
from app.core.services.database_service import DatabaseService
from app.mame.executable import MameExecutable

class ImportWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, mame_path, db_service: DatabaseService):
        super().__init__()
        self.mame_path = mame_path
        self.db_service = db_service

    def run(self):
        try:
            self.progress.emit(0, "Obtendo listxml do MAME...")
            mame = MameExecutable(self.mame_path)
            xml = mame.get_listxml()
            version = mame.version
            self.progress.emit(50, "Importando dados para o banco...")
            self.db_service.import_listxml(xml, str(self.mame_path), version)
            self.progress.emit(100, "Importação concluída!")
            self.finished.emit(True, "Importação bem-sucedida.")
        except Exception as e:
            self.finished.emit(False, f"Erro: {e}")