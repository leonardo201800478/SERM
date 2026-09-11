"""Tradução runtime das superfícies GUI do SERM V2."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton, QComboBox, QGroupBox, QLabel, QTabWidget, QWidget

from .ui_preferences import UiPreferences


TEXTS = {
    "pt-BR": {
        "Filtros": "Filtros",
        "Filtros e Curadoria": "Filtros e Curadoria",
        "MAME — FILTROS": "MAME — FILTROS",
        "Classificação → curadoria → filtragem física → reconstrução. Configure os critérios abaixo e acompanhe o resultado no preview.": "Classificação → curadoria → filtragem física → reconstrução. Configure os critérios abaixo e acompanhe o resultado no preview.",
        "SCAN DE ENTRADA": "SCAN DE ENTRADA",
        "ATUALIZAR": "ATUALIZAR",
        "1 — TIPO DE JOGOS": "1 — TIPO DE JOGOS",
        "2 — CURADORIA": "2 — CURADORIA",
        "3 — TIPO DE SET": "3 — TIPO DE SET",
        "4 — Reconstrução": "4 — Reconstrução",
        "CLASSIFICAÇÃO DO JOGO": "CLASSIFICAÇÃO DO JOGO",
        "Marque os tipos que devem ser EXCLUÍDOS do set final. A classificação vem congelada do snapshot do scan.": "Marque os tipos que devem ser EXCLUÍDOS do set final. A classificação vem congelada do snapshot do scan.",
        "FORMATO DO SET": "FORMATO DO SET",
        "SELEÇÃO DE MÁQUINAS": "SELEÇÃO DE MÁQUINAS",
        "NOVO PERFIL": "NOVO PERFIL",
        "SALVAR FILTROS": "SALVAR FILTROS",
        "APLICAR E GERAR ARQUIVO": "APLICAR E GERAR ARQUIVO",
        "RESULTADO": "RESULTADO",
        "PREFERÊNCIAS DE SELEÇÃO": "PREFERÊNCIAS DE SELEÇÃO",
        "REGRAS DA CURADORIA": "REGRAS DA CURADORIA",
        "A curadoria escolhe as machines antes da montagem do SET. O scan original permanece intacto e cada exclusão gera uma decisão auditável.": "A curadoria escolhe as machines antes da montagem do SET. O scan original permanece intacto e cada exclusão gera uma decisão auditável.",
        "Regiões:": "Regiões:", "Idiomas:": "Idiomas:", "Máx. jogadores:": "Máx. jogadores:", "Máx. botões:": "Máx. botões:", "Controles:": "Controles:", "Direções:": "Direções:",
        "Orientação:": "Orientação:", "Permitir clones": "Permitir clones", "Permitir bootlegs": "Permitir bootlegs", "Permitir protótipos": "Permitir protótipos", "1G1R — um representante por família parent/clone": "1G1R — um representante por família parent/clone",
        "Qualidade mínima:": "Qualidade mínima:", "Exigir todos os controles/direções informados": "Exigir todos os controles/direções informados",
        "Incluir BIOS / sets de BIOS": "Incluir BIOS / sets de BIOS", "Incluir Devices": "Incluir Devices", "Incluir CHDs / disks": "Incluir CHDs / disks", "Incluir ROMs opcionais": "Incluir ROMs opcionais", "Somente máquinas working": "Somente máquinas working",
        "Com clones": "Com clones", "Somente parents": "Somente parents", "Split — arquivos dependentes separados": "Split — arquivos dependentes separados", "Non-Merged — cada set independente": "Non-Merged — cada set independente", "Full-Merged — parent + clones no mesmo set": "Full-Merged — parent + clones no mesmo set",
    },
    "en": {
        "Filtros": "Filters", "Filtros e Curadoria": "Filters & Curation", "MAME — FILTROS": "MAME — FILTERS",
        "Classificação → curadoria → filtragem física → reconstrução. Configure os critérios abaixo e acompanhe o resultado no preview.": "Classification → curation → physical filtering → reconstruction. Configure the criteria below and review the preview.",
        "SCAN DE ENTRADA": "INPUT SCAN", "ATUALIZAR": "REFRESH", "1 — TIPO DE JOGOS": "1 — GAME TYPES", "2 — CURADORIA": "2 — CURATION", "3 — TIPO DE SET": "3 — SET TYPE", "4 — Reconstrução": "4 — Reconstruction",
        "CLASSIFICAÇÃO DO JOGO": "GAME CLASSIFICATION", "Marque os tipos que devem ser EXCLUÍDOS do set final. A classificação vem congelada do snapshot do scan.": "Select the types that must be EXCLUDED from the final set. Classification is frozen in the scan snapshot.",
        "FORMATO DO SET": "SET FORMAT", "SELEÇÃO DE MÁQUINAS": "MACHINE SELECTION", "NOVO PERFIL": "NEW PROFILE", "SALVAR FILTROS": "SAVE FILTERS", "APLICAR E GERAR ARQUIVO": "APPLY & GENERATE FILE", "RESULTADO": "RESULT",
        "PREFERÊNCIAS DE SELEÇÃO": "SELECTION PREFERENCES", "REGRAS DA CURADORIA": "CURATION RULES",
        "A curadoria escolhe as machines antes da montagem do SET. O scan original permanece intacto e cada exclusão gera uma decisão auditável.": "Curation selects machines before SET assembly. The original scan remains intact and every exclusion produces an auditable decision.",
        "Regiões:": "Regions:", "Idiomas:": "Languages:", "Máx. jogadores:": "Max players:", "Máx. botões:": "Max buttons:", "Controles:": "Controls:", "Direções:": "Directions:", "Orientação:": "Orientation:",
        "Permitir clones": "Allow clones", "Permitir bootlegs": "Allow bootlegs", "Permitir protótipos": "Allow prototypes", "1G1R — um representante por família parent/clone": "1G1R — one representative per parent/clone family", "Qualidade mínima:": "Minimum quality:", "Exigir todos os controles/direções informados": "Require all specified controls/directions",
        "Incluir BIOS / sets de BIOS": "Include BIOS / BIOS sets", "Incluir Devices": "Include Devices", "Incluir CHDs / disks": "Include CHDs / disks", "Incluir ROMs opcionais": "Include optional ROMs", "Somente máquinas working": "Working machines only",
        "Com clones": "With clones", "Somente parents": "Parents only", "Split — arquivos dependentes separados": "Split — dependent files separate", "Non-Merged — cada set independente": "Non-Merged — each set independent", "Full-Merged — parent + clones no mesmo set": "Full-Merged — parent + clones in the same set",
    },
    "es": {
        "Filtros": "Filtros", "Filtros e Curadoria": "Filtros y Curaduría", "MAME — FILTROS": "MAME — FILTROS",
        "Classificação → curadoria → filtragem física → reconstrução. Configure os critérios abaixo e acompanhe o resultado no preview.": "Clasificación → curaduría → filtrado físico → reconstrucción. Configure los criterios y revise la vista previa.",
        "SCAN DE ENTRADA": "ESCANEO DE ENTRADA", "ATUALIZAR": "ACTUALIZAR", "1 — TIPO DE JOGOS": "1 — TIPOS DE JUEGO", "2 — CURADORIA": "2 — CURADURÍA", "3 — TIPO DE SET": "3 — TIPO DE SET", "4 — Reconstrução": "4 — Reconstrucción",
        "CLASSIFICAÇÃO DO JOGO": "CLASIFICACIÓN DEL JUEGO", "Marque os tipos que devem ser EXCLUÍDOS do set final. A classificação vem congelada do snapshot do scan.": "Seleccione los tipos que deben EXCLUIRSE del set final. La clasificación queda congelada en el snapshot.",
        "FORMATO DO SET": "FORMATO DEL SET", "SELEÇÃO DE MÁQUINAS": "SELECCIÓN DE MÁQUINAS", "NOVO PERFIL": "NUEVO PERFIL", "SALVAR FILTROS": "GUARDAR FILTROS", "APLICAR E GERAR ARQUIVO": "APLICAR Y GENERAR ARCHIVO", "RESULTADO": "RESULTADO",
        "PREFERÊNCIAS DE SELEÇÃO": "PREFERENCIAS DE SELECCIÓN", "REGRAS DA CURADORIA": "REGLAS DE CURADURÍA", "A curadoria escolhe as machines antes da montagem do SET. O scan original permanece intacto e cada exclusão gera uma decisão auditável.": "La curaduría selecciona las máquinas antes de montar el SET. El escaneo original permanece intacto y cada exclusión genera una decisión auditable.",
        "Regiões:": "Regiones:", "Idiomas:": "Idiomas:", "Máx. jogadores:": "Máx. jugadores:", "Máx. botões:": "Máx. botones:", "Controles:": "Controles:", "Direções:": "Direcciones:", "Orientação:": "Orientación:",
        "Permitir clones": "Permitir clones", "Permitir bootlegs": "Permitir bootlegs", "Permitir protótipos": "Permitir prototipos", "1G1R — um representante por família parent/clone": "1G1R — un representante por familia parent/clone", "Qualidade mínima:": "Calidad mínima:", "Exigir todos os controles/direções informados": "Exigir todos los controles/direcciones indicados",
        "Incluir BIOS / sets de BIOS": "Incluir BIOS / conjuntos BIOS", "Incluir Devices": "Incluir dispositivos", "Incluir CHDs / disks": "Incluir CHDs / discos", "Incluir ROMs opcionais": "Incluir ROMs opcionales", "Somente máquinas working": "Solo máquinas funcionales",
        "Com clones": "Con clones", "Somente parents": "Solo parents", "Split — arquivos dependentes separados": "Split — archivos dependientes separados", "Non-Merged — cada set independente": "Non-Merged — cada set independiente", "Full-Merged — parent + clones no mesmo set": "Full-Merged — parent + clones en el mismo set",
    },
}


def retranslate_widget_tree(root: QWidget, language: str | None = None) -> int:
    """Traduz textos conhecidos da árvore sem alterar valores técnicos do pipeline."""
    lang = language or UiPreferences.language()
    catalog = TEXTS.get(lang, TEXTS["pt-BR"])
    changed = 0
    for widget in root.findChildren(QWidget):
        if isinstance(widget, QLabel):
            current = widget.text()
            translated = catalog.get(current)
            if translated is not None and translated != current:
                widget.setText(translated)
                changed += 1
        elif isinstance(widget, QGroupBox):
            current = widget.title()
            translated = catalog.get(current)
            if translated is not None and translated != current:
                widget.setTitle(translated)
                changed += 1
        elif isinstance(widget, QAbstractButton):
            current = widget.text()
            translated = catalog.get(current)
            if translated is not None and translated != current:
                widget.setText(translated)
                changed += 1
        elif isinstance(widget, QComboBox):
            for index in range(widget.count()):
                current = widget.itemText(index)
                translated = catalog.get(current)
                if translated is not None and translated != current:
                    widget.setItemText(index, translated)
                    changed += 1
        elif isinstance(widget, QTabWidget):
            for index in range(widget.count()):
                current = widget.tabText(index)
                translated = catalog.get(current)
                if translated is not None and translated != current:
                    widget.setTabText(index, translated)
                    changed += 1
    return changed


__all__ = ["TEXTS", "retranslate_widget_tree"]
