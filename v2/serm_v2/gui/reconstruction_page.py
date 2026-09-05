"""Guia reservada para a reconstrução do SET após o scan."""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class ReconstructionPage(QWidget):
    """Recebe o mesmo perfil do filtro e o resultado do scan posteriormente."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profile: Any | None = None
        self._scan_result: Any | None = None
        layout = QVBoxLayout(self)
        title = QLabel("SERM V2 — Reconstrução de ROMs")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel(
            "A reconstrução não redefine o filtro. Ela recebe o profile_id e o contexto "
            "do scan para montar o plano de restauração do SET, preservando a separação "
            "entre seleção, verificação e reconstrução."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        context_box = QGroupBox("Contexto recebido")
        context_layout = QVBoxLayout(context_box)
        self.profile_label = QLabel("Perfil: nenhum")
        self.scan_label = QLabel("Scan: ainda não executado")
        self.source_label = QLabel("Fonte: —")
        for label in (self.profile_label, self.scan_label, self.source_label):
            label.setWordWrap(True)
            context_layout.addWidget(label)
        layout.addWidget(context_box)

        action_box = QGroupBox("Planejamento")
        action_layout = QHBoxLayout(action_box)
        self.plan_button = QPushButton("GERAR PLANO DE RECONSTRUÇÃO")
        self.plan_button.setEnabled(False)
        self.execute_button = QPushButton("EXECUTAR RECONSTRUÇÃO")
        self.execute_button.setEnabled(False)
        action_layout.addWidget(self.plan_button)
        action_layout.addWidget(self.execute_button)
        action_layout.addStretch()
        layout.addWidget(action_box)

        self.status = QLabel(
            "Aguardando um resultado persistido do scan. Quando o scanner V2 estiver "
            "conectado, o plano será gerado a partir do mesmo perfil e do mesmo scan."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()

    def set_scan_context(self, profile: Any, scan_result: Any | None = None) -> None:
        """Recebe o perfil salvo; scan_result será ligado ao motor físico depois."""
        self._profile = profile
        self._scan_result = scan_result
        profile_name = getattr(profile, "name", None) or str(profile.get("name", "Perfil")) if isinstance(profile, dict) else getattr(profile, "name", "Perfil")
        profile_id = getattr(profile, "profile_id", None) or (str(profile.get("profile_id", "")) if isinstance(profile, dict) else "")
        source = getattr(profile, "source", None) or (str(profile.get("source", "")) if isinstance(profile, dict) else "")
        system = getattr(profile, "system", None) or (str(profile.get("system", "")) if isinstance(profile, dict) else "")
        self.profile_label.setText(f"Perfil: {profile_name}\nID: {profile_id}")
        self.source_label.setText(f"Fonte: {source} › {system}")
        if scan_result is None:
            self.scan_label.setText("Scan: preparado; aguardando resultado do scanner")
            self.plan_button.setEnabled(False)
            self.execute_button.setEnabled(False)
        else:
            self._scan_result = scan_result
            self.scan_label.setText(f"Scan: resultado recebido — {scan_result}")
            self.plan_button.setEnabled(True)
            self.execute_button.setEnabled(False)

    def set_scan_result(self, scan_result: Any) -> None:
        """Atualiza a reconstrução quando o motor persistir o resultado do scan."""
        if self._profile is None:
            return
        self.set_scan_context(self._profile, scan_result)
        self.status.setText("Resultado do scan recebido. O próximo passo é gerar o plano de reconstrução.")

    def refresh(self) -> None:
        """Mantém o contexto selecionado ao revisitar a guia."""
        return


__all__ = ["ReconstructionPage"]
