"""Guia de reconstrução de ROMs do SERM V2.

A reconstrução consome o resultado de um scan e o perfil que originou esse
scan; ela não redefine filtros nem executa um novo inventário físico.
"""
from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget


class ReconstructionPage(QWidget):
    """Superfície dedicada ao planejamento e à execução da reconstrução."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("SERM V2 — Reconstrução de ROMs")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel("A reconstrução é a etapa posterior ao scan. Ela recebe o perfil salvo e os achados do scanner, calcula o que pode ser reaproveitado e apresenta um plano antes de qualquer alteração física.")
        description.setWordWrap(True)
        layout.addWidget(description)
        source = QGroupBox("Entrada da reconstrução")
        source_layout = QVBoxLayout(source)
        self.profile_label = QLabel("Perfil: nenhum scan selecionado")
        self.scan_label = QLabel("Scan: nenhum resultado disponível")
        source_layout.addWidget(self.profile_label)
        source_layout.addWidget(self.scan_label)
        layout.addWidget(source)
        plan = QGroupBox("Plano")
        plan_layout = QVBoxLayout(plan)
        self.plan_list = QListWidget()
        self.plan_list.addItems(["Reutilizar ROMs válidas encontradas pelo scan", "Reconstruir conjuntos a partir de parents/clones e dependências", "Reaproveitar membros de arquivos quando o formato do set permitir", "Planejar CHDs e demais mídias sem destruir fontes originais", "Mostrar conflitos e itens sem resolução antes da execução"])
        plan_layout.addWidget(self.plan_list)
        layout.addWidget(plan, 1)
        actions = QHBoxLayout()
        self.plan_button = QPushButton("GERAR PLANO DE RECONSTRUÇÃO"); self.plan_button.setEnabled(False)
        self.execute_button = QPushButton("EXECUTAR RECONSTRUÇÃO"); self.execute_button.setEnabled(False)
        actions.addWidget(self.plan_button); actions.addWidget(self.execute_button); actions.addStretch(); layout.addLayout(actions)
        self.status = QLabel("Aguardando um scan concluído. Nenhuma alteração será feita automaticamente."); self.status.setWordWrap(True); layout.addWidget(self.status)

    def set_scan_context(self, profile, scan_result=None) -> None:
        source = getattr(profile, "source", "?"); system = getattr(profile, "system", "?")
        self.profile_label.setText(f"Perfil: {source} › {system}")
        self.scan_label.setText("Scan: resultado recebido; planejador pronto" if scan_result is not None else "Scan: perfil recebido, aguardando resultado")
        self.plan_button.setEnabled(scan_result is not None)
        self.status.setText("Contexto de reconstrução carregado; o plano ainda precisa ser revisado antes da execução.")

    def refresh(self) -> None:
        return None


__all__ = ["ReconstructionPage"]
