"""Interface para a reconstrução do catálogo MAME."""
from __future__ import annotations
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QProgressBar,QLabel,QPlainTextEdit
from app.config.app_config import AppConfig
from app.mame.dataset_builder import MameDatasetBuilder

class DatasetWorker(QThread):
    """Executa o pipeline fora da thread da interface."""
    progress=Signal(int,str); finished_ok=Signal(dict); failed=Signal(str)
    def __init__(self,db,config):super().__init__();self.db=db;self.config=config;self.cancelled=False
    def run(self):
        try:
            result=MameDatasetBuilder(self.db,self.config).run(self._progress,self._cancel)
            self.finished_ok.emit(result)
        except Exception as exc:self.failed.emit(str(exc))
    def _progress(self,value,message):self.progress.emit(value,message)
    def _cancel(self):return self.cancelled
    def stop(self):self.cancelled=True

class DatasetTab(QWidget):
    """Controla a criação completa do dataset MAME."""
    def __init__(self,parent=None):
        super().__init__(parent);self.parent_window=parent;self.worker=None;self.config=AppConfig();self._ui()
    def _ui(self):
        """Monta controles de execução, progresso e log."""
        layout=QVBoxLayout(self)
        title=QLabel("Base MAME / CatVer / CHD");title.setStyleSheet("font-size:20px;font-weight:bold")
        layout.addWidget(title)
        layout.addWidget(QLabel("Um único processo gera o LISTXML, recria as tabelas do catálogo, importa CatVer e verifica CHDs com chdman."))
        row=QHBoxLayout();self.start=QPushButton("Construir / Atualizar base MAME");self.stop=QPushButton("Cancelar");self.stop.setEnabled(False);row.addWidget(self.start);row.addWidget(self.stop);row.addStretch();layout.addLayout(row)
        self.status=QLabel("Pronto");layout.addWidget(self.status)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.setValue(0);layout.addWidget(self.progress)
        self.log=QPlainTextEdit();self.log.setReadOnly(True);layout.addWidget(self.log,1)
        self.start.clicked.connect(self.start_build);self.stop.clicked.connect(self.stop_build)
    def start_build(self):
        """Inicia o pipeline de dataset."""
        if self.worker and self.worker.isRunning():return
        self.config=AppConfig();self.log.clear();self.status.setText("Executando...");self.start.setEnabled(False);self.stop.setEnabled(True);self.progress.setRange(0,0)
        db=self.parent_window.db
        self.worker=DatasetWorker(db,self.config);self.worker.progress.connect(self.on_progress);self.worker.finished_ok.connect(self.on_finished);self.worker.failed.connect(self.on_failed);self.worker.start()
    def stop_build(self):
        """Solicita cancelamento seguro."""
        if self.worker:self.worker.stop();self.status.setText("Cancelando...")
    def on_progress(self,value,message):
        """Atualiza progresso e log da execução."""
        self.status.setText(message);self.log.appendPlainText(message)
    def on_finished(self,result):
        """Finaliza a UI após sucesso."""
        self.start.setEnabled(True);self.stop.setEnabled(False);self.progress.setRange(0,100);self.progress.setValue(100);self.status.setText("Concluído");self.log.appendPlainText(str(result));self.worker=None
        if hasattr(self.parent_window,"_on_database_updated"):self.parent_window._on_database_updated()
    def on_failed(self,error):
        """Mostra falha sem deixar a interface bloqueada."""
        self.start.setEnabled(True);self.stop.setEnabled(False);self.progress.setRange(0,100);self.status.setText("Falha");self.log.appendPlainText("ERRO: "+error);self.worker=None
