"""Gerenciamento separado de shaders e bezels do SERM V2.

A tela respeita a diferença entre recursos nativos e camadas externas:
- MAME e RetroArch possuem configuração nativa de shaders/artework/overlays;
- FBNeo possui efeitos de vídeo nativos, mas não um sistema genérico de bezel;
- Flycast possui filtros/renderização e caminhos de texturas, mas não um sistema
  nativo de bezel comparável ao RetroArch;
- Supermodel não possui uma camada nativa genérica de shader/bezel no INI.

Quando uma chave existe no arquivo real, a edição usa ConfigFileEditor, com
backup e gravação atômica. Recursos não nativos são apenas catalogados pelo SERM,
sem inventar chaves no arquivo do emulador.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from .directories_guide_page import ConfigFileEditor


@dataclass(frozen=True, slots=True)
class LayerSpec:
    """Define uma opção de shader/bezel e sua chave nativa, quando existir."""

    key: str
    label: str
    description: str
    kind: str = "text"


class EmulatorShadersBezelsPage(QWidget):
    """Exibe cada emulador no nível 2 e Shaders/Bezels no nível 3."""

    PAGE_TITLE = "Shaders / Bezels"
    PATHS_FILE = data_root() / "emulator_paths.json"
    ASSETS_FILE = data_root() / "emulator_visual_assets.json"
    CONFIG_KEYS = {
        "mame": "mame_config",
        "fbneo": "fbneo_config",
        "flycast": "flycast_config",
        "supermodel": "supermodel_config",
        "retroarch": "retroarch_cfg",
    }
    LABELS = {
        "mame": "MAME",
        "fbneo": "FBNeo",
        "flycast": "Flycast",
        "supermodel": "Supermodel",
        "retroarch": "RetroArch",
    }

    SHADERS: dict[str, tuple[LayerSpec, ...]] = {
        "mame": (
            LayerSpec("bgfx_path", "Diretório BGFX", "Diretório onde o MAME procura shaders BGFX."),
            LayerSpec(
                "bgfx_screen_chains",
                "Screen chain",
                "Cadeia BGFX aplicada às telas. Exemplos documentados: default, unfiltered, hlsl, crt-geom, crt-geom-deluxe e lcd-grid.",
            ),
            LayerSpec(
                "bgfx_shadow_mask", "Shadow mask", "Arquivo PNG de shadow mask usado pelo BGFX."
            ),
            LayerSpec(
                "bgfx_vectorcrt",
                "Vector CRT",
                "Ativa o renderer CRT persistente para jogos vetoriais.",
            ),
            LayerSpec("gl_glsl", "GLSL", "Ativa o pipeline GLSL legado do MAME."),
            LayerSpec("gl_glsl_filter", "Filtro GLSL", "Filtragem aplicada à saída GLSL."),
            LayerSpec(
                "glsl_shader_mame0",
                "GLSL shader 0",
                "Primeiro shader da cadeia GLSL; os demais podem ser mantidos por edição avançada.",
            ),
        ),
        "fbneo": (
            LayerSpec("nVidDX9HardFX", "HardFX", "Índice do efeito HardFX do blitter DirectX 9."),
            LayerSpec("bVidDX9Bilinear", "Bilinear", "Ativa filtragem bilinear no blitter DX9."),
            LayerSpec("bVidScanlines", "Scanlines", "Ativa scanlines no pipeline de vídeo."),
            LayerSpec(
                "bVidScanDelay",
                "Scan delay / phosphor",
                "Ativa o efeito de persistência de fósforo documentado pelo template do FBNeo.",
            ),
            LayerSpec("bVidMotionBlur", "Motion blur", "Ativa motion blur do vídeo."),
            LayerSpec("bVidHardwareVertex", "Hardware vertex", "Usa hardware vertex processing."),
        ),
        "flycast": (
            LayerSpec(
                "rend.LinearInterpolation",
                "Linear interpolation",
                "Filtragem linear da imagem renderizada.",
            ),
            LayerSpec(
                "rend.TextureFiltering",
                "Texture filtering",
                "Modo de filtragem de texturas do renderer.",
            ),
            LayerSpec("rend.TextureUpscale2", "Texture upscale", "Fator de upscale das texturas."),
            LayerSpec(
                "rend.MaxFilteredTextureSize", "Max filtered texture", "Limite da textura filtrada."
            ),
            LayerSpec(
                "rend.CustomTextures",
                "Custom textures",
                "Habilita substituição por texturas personalizadas.",
            ),
            LayerSpec(
                "rend.PreloadCustomTextures",
                "Preload custom textures",
                "Pré-carrega texturas personalizadas.",
            ),
        ),
        "supermodel": (),
        "retroarch": (
            LayerSpec(
                "video_shader_enable",
                "Shader habilitado",
                "Ativa o shader configurado pelo RetroArch.",
            ),
            LayerSpec(
                "video_shader",
                "Shader / preset",
                "Caminho do shader ou preset. RetroArch aceita presets como .slangp, .glslp e .cgp conforme o pipeline.",
            ),
            LayerSpec(
                "video_shader_dir",
                "Diretório de shaders",
                "Diretório padrão usado pelo RetroArch para shaders.",
            ),
            LayerSpec(
                "video_shader_watch_files",
                "Watch files",
                "Monitora alterações nos arquivos de shader quando suportado.",
            ),
            LayerSpec(
                "video_shader_remember_last_dir",
                "Lembrar diretório",
                "Mantém o último diretório de shader utilizado.",
            ),
        ),
    }

    BEZELS: dict[str, tuple[LayerSpec, ...]] = {
        "mame": (
            LayerSpec(
                "artpath",
                "Diretório de artwork",
                "Diretório onde o MAME procura artwork e layouts.",
            ),
            LayerSpec(
                "fallback_artwork",
                "Fallback artwork",
                "Artwork/layout usado quando o sistema não possui um artwork específico.",
            ),
            LayerSpec(
                "override_artwork",
                "Override artwork",
                "Substitui o artwork selecionado por um layout específico.",
            ),
            LayerSpec(
                "artwork_crop", "Cortar artwork", "Recorta artwork para preencher a área de vídeo."
            ),
        ),
        "fbneo": (),
        "flycast": (),
        "supermodel": (),
        "retroarch": (
            LayerSpec(
                "input_overlay_enable",
                "Overlay habilitado",
                "Ativa o sistema de overlays do RetroArch.",
            ),
            LayerSpec(
                "input_overlay",
                "Overlay / bezel",
                "Caminho do arquivo .cfg do overlay. Overlays decorativos podem funcionar como bezel.",
            ),
            LayerSpec("input_overlay_opacity", "Opacidade", "Opacidade do overlay."),
            LayerSpec("input_overlay_scale", "Escala", "Escala do overlay."),
            LayerSpec(
                "input_overlay_hide_in_menu",
                "Ocultar no menu",
                "Oculta o overlay enquanto o menu está aberto.",
            ),
            LayerSpec(
                "input_overlay_enable_autopreferred",
                "Autopreferido",
                "Permite seleção automática do overlay preferido quando disponível.",
            ),
        ),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controls: dict[tuple[str, str, str], QLineEdit] = {}
        self.status: dict[tuple[str, str], QLabel] = {}
        self._build_ui()
        self.refresh()

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        """Carrega JSON pertencente ao SERM sem lançar exceções de I/O para a GUI."""
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _save_json(path: Path, value: dict[str, Any]) -> None:
        """Persiste o catálogo de assets do SERM em JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _editor(self, emulator: str) -> ConfigFileEditor | None:
        """Abre o arquivo configurado para o emulador."""
        paths = self._load_json(self.PATHS_FILE)
        raw = paths.get(self.CONFIG_KEYS[emulator])
        if not raw:
            return None
        path = Path(str(raw)).expanduser()
        if not path.is_file():
            return None
        try:
            return ConfigFileEditor(path)
        except OSError:
            return None

    def _build_ui(self) -> None:
        """Cria nível 2 por emulador e nível 3 por camada visual."""
        root = QVBoxLayout(self)
        title = QLabel(self.PAGE_TITLE)
        title.setProperty("role", "title")
        root.addWidget(title)
        info = QLabel(
            "Shaders e Bezels são tratados separadamente. Chaves só ficam editáveis quando existem no arquivo real; camadas não nativas não inventam configurações do emulador."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        self.emulators = QTabWidget()
        for emulator, label in self.LABELS.items():
            page = QWidget()
            layout = QVBoxLayout(page)
            layers = QTabWidget()
            layers.addTab(self._layer_page(emulator, "shader", self.SHADERS[emulator]), "Shaders")
            layers.addTab(self._layer_page(emulator, "bezel", self.BEZELS[emulator]), "Bezels")
            layout.addWidget(layers, 1)
            self.emulators.addTab(page, label)
        root.addWidget(self.emulators, 1)

    def _layer_page(self, emulator: str, layer: str, specs: tuple[LayerSpec, ...]) -> QWidget:
        """Monta uma camada visual com status, arquivo e opções nativas."""
        page = QWidget()
        outer = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setContentsMargins(14, 14, 14, 14)
        status = QLabel()
        status.setObjectName(f"visual_status_{emulator}_{layer}")
        self.status[(emulator, layer)] = status
        form.addRow("Status", status)

        if not specs:
            native = QLabel(self._unsupported_message(emulator, layer))
            native.setWordWrap(True)
            form.addRow("Camada", native)
        else:
            for spec in specs:
                edit = QLineEdit()
                edit.setPlaceholderText("Não presente no arquivo")
                edit.setToolTip(spec.description)
                self.controls[(emulator, layer, spec.key)] = edit
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.addWidget(edit, 1)
                if spec.key.endswith(
                    (
                        "_path",
                        "_dir",
                        "artpath",
                        "fallback_artwork",
                        "override_artwork",
                        "input_overlay",
                        "video_shader",
                    )
                ):
                    browse = QPushButton("...")
                    browse.setMaximumWidth(42)
                    browse.clicked.connect(
                        lambda _=False, e=emulator, layer_name=layer, k=spec.key: self._browse(e, layer_name, k)
                    )
                    row_layout.addWidget(browse)
                form.addRow(spec.label, row)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        buttons = QHBoxLayout()
        save = QPushButton("Salvar")
        save.setProperty("role", "primary")
        save.clicked.connect(lambda _=False, e=emulator, layer_name=layer: self.save(e, layer_name))
        refresh = QPushButton("Recarregar")
        refresh.clicked.connect(self.refresh)
        buttons.addStretch(1)
        buttons.addWidget(refresh)
        buttons.addWidget(save)
        outer.addLayout(buttons)
        return page

    @staticmethod
    def _unsupported_message(emulator: str, layer: str) -> str:
        """Explica quando o emulador não possui uma camada nativa equivalente."""
        if emulator == "supermodel":
            return "O Supermodel não expõe no Supermodel.ini uma cadeia genérica nativa de shaders ou um sistema nativo de bezels equivalente ao MAME/RetroArch. O SERM não criará chaves fictícias; esta camada fica reservada para integração externa futura."
        if emulator == "fbneo":
            return "O FBNeo não possui no arquivo atual um sistema genérico de bezel. Os efeitos de vídeo ficam separados na camada Shaders; bezels devem ser tratados por artwork/frontend externo."
        if emulator == "flycast":
            return "O Flycast standalone não possui no emu.cfg uma camada genérica de bezel equivalente ao overlay do RetroArch. A camada Shaders expõe filtros/renderização nativos; bezels ficam reservados para integração externa."
        return "Não há configuração nativa catalogada para esta camada."

    @staticmethod
    def _raw_value(editor: ConfigFileEditor, key: str) -> str:
        """Obtém o primeiro valor da chave, normalizando aspas apenas para a GUI."""
        values = editor.values(key)
        return values[0] if values else ""

    def _browse(self, emulator: str, layer: str, key: str) -> None:
        """Seleciona arquivo/diretório e coloca o caminho no campo visual."""
        current = self.controls[(emulator, layer, key)].text().strip()
        if key.endswith(("_path", "_dir", "artpath")):
            selected = QFileDialog.getExistingDirectory(
                self, "Selecionar diretório", current or str(Path.home())
            )
        else:
            selected, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar arquivo",
                current or str(Path.home()),
                "Arquivos visuais (*.png *.jpg *.jpeg *.cfg *.slang *.slangp *.glsl *.glslp *.cgp);;Todos os arquivos (*)",
            )
        if selected:
            self.controls[(emulator, layer, key)].setText(str(Path(selected).resolve()))

    def refresh(self) -> None:
        """Lê novamente os arquivos e preenche as duas camadas sem gravar."""
        for emulator in self.LABELS:
            editor = self._editor(emulator)
            for layer, specs in (
                ("shader", self.SHADERS[emulator]),
                ("bezel", self.BEZELS[emulator]),
            ):
                status = self.status[(emulator, layer)]
                if editor is None:
                    status.setText("Arquivo não configurado / não encontrado")
                    for spec in specs:
                        self.controls[(emulator, layer, spec.key)].setEnabled(False)
                    continue
                status.setText(f"Arquivo: {editor.path}")
                for spec in specs:
                    control = self.controls[(emulator, layer, spec.key)]
                    value = self._raw_value(editor, spec.key)
                    control.setEnabled(bool(value or editor.values(spec.key)))
                    control.setText(value)

    def save(self, emulator: str, layer: str) -> None:
        """Grava somente as chaves nativas existentes, preservando o arquivo."""
        editor = self._editor(emulator)
        if editor is None:
            QMessageBox.warning(
                self,
                self.PAGE_TITLE,
                "Arquivo de configuração não encontrado. Configure-o primeiro na guia Diretórios.",
            )
            return
        specs = self.SHADERS[emulator] if layer == "shader" else self.BEZELS[emulator]
        changed = 0
        try:
            for spec in specs:
                old_values = editor.values(spec.key)
                if not old_values:
                    continue
                new_value = self.controls[(emulator, layer, spec.key)].text().strip()
                old_value = old_values[0].strip().strip('"')
                if new_value != old_value:
                    editor.set_value(spec.key, new_value)
                    changed += 1
            if not changed:
                QMessageBox.information(self, self.PAGE_TITLE, "Nenhuma alteração pendente.")
                return
            backup = editor.save()
        except Exception as exc:
            QMessageBox.critical(
                self, "Falha ao salvar", f"Nenhuma alteração foi concluída com segurança.\n\n{exc}"
            )
            return
        self.refresh()
        QMessageBox.information(
            self, "Configuração salva", f"{changed} opção(ões) alterada(s).\nBackup:\n{backup}"
        )


__all__ = ["EmulatorShadersBezelsPage", "LayerSpec"]
