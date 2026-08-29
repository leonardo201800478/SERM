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
            mame = MameExecutable(self.mame_path)

            def on_progress(count: int, message: str):
                # Reserva 0-100 proporcional a um total desconhecido: como
                # não sabemos o total de máquinas de antemão (streaming),
                # reportamos progresso "indeterminado" via contagem bruta.
                self.progress.emit(min(99, count // 100), message)

            total = self.db_service.import_from_executable(mame, progress_callback=on_progress)
            self.progress.emit(100, "Importação concluída!")
            self.finished.emit(True, f"Importação bem-sucedida: {total} máquinas.")
        except Exception as e:
            self.finished.emit(False, f"Erro: {e}")