"""Configuração central dos diretórios dos quatro emuladores.

A aba possui uma subaba por emulador: MAME, Flycast, Supermodel e FBNeo.
O MAME usa o mame.ini real como fonte de verdade; os demais caminhos são
persistidos em AppConfig.emulator_paths para uso compartilhado pelo aplicativo.
"""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFormLayout,QGroupBox,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QScrollArea,QTabWidget,QVBoxLayout,QWidget,QFileDialog)
from app.config.app_config import AppConfig
from app.core.services.ini_service import IniService
from app.mame.executable import MameExecutable

class DirectoriesTab(QWidget):
    """Aba central de diretórios, organizada por emulador."""
    EMULATORS=(('mame','MAME'),('flycast','Flycast'),('supermodel','Supermodel'),('fbneo','FBNeo'))
    EXECUTABLES={'mame':'mame.exe','flycast':'flycast.exe','supermodel':'supermodel.exe','fbneo':'fbneo64.exe'}
    PATH_LABELS={
        'flycast':(('roms','ROMs / conteúdo'),('bios','BIOS'),('vmu','VMU'),('saves','Saves'),('states','Save states'),('textures','Textures'),('boxart','Boxart'),('cheats','Cheats')),
        'supermodel':(('roms','ROMs'),('config','Config'),('nvram','NVRAM'),('saves','Saves / save states'),('assets','Assets')),
        'fbneo':(('roms','ROMs'),('bios','BIOS / ROM suplementar'),('samples','Samples'),('cheats','Cheats'),('previews','Previews'),('titles','Titles'),('snapshots','Snapshots'),('history','History'),('icons','Icons')),
    }
    settings_changed=Signal()
    def __init__(self,parent:QWidget|None=None)->None:
        super().__init__(parent); self.parent_window=parent; self.config=getattr(parent,'config',None) or AppConfig(); self.ini_service=None; self.mame_exec=None; self.emulator_dir_edits={}; self.emulator_status_labels={}; self.path_edits={}; self._setup_ui(); self._refresh_ui_state()
    def _setup_ui(self)->None:
        """Cria a aba principal e as quatro subabas de emuladores."""
        root=QVBoxLayout(self); title=QLabel('Diretórios dos emuladores'); title.setStyleSheet('font-size:20px;font-weight:bold;'); root.addWidget(title)
        info=QLabel('Cada emulador possui sua própria instalação e seus diretórios de conteúdo. As configurações são compartilhadas com Home, Catálogos, Scan e Reconstrução.'); info.setWordWrap(True); info.setStyleSheet('color:#888;padding-bottom:4px;'); root.addWidget(info)
        self.subtabs=QTabWidget(); root.addWidget(self.subtabs,1)
        for key,label in self.EMULATORS:self.subtabs.addTab(self._create_emulator_page(key,label),label)
    def _create_emulator_page(self,key:str,label:str)->QWidget:
        """Cria a página rolável de um emulador."""
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); container=QWidget(); layout=QVBoxLayout(container)
        installation=QGroupBox(f'Instalação do {label}'); form=QFormLayout(installation); directory=QLineEdit(); directory.setReadOnly(True); directory.setPlaceholderText('Diretório de instalação'); browse=QPushButton('Selecionar…'); browse.clicked.connect(lambda _=False,k=key:self._select_emulator_directory(k)); row=QHBoxLayout(); row.addWidget(directory,1); row.addWidget(browse); form.addRow('Diretório:',row); executable=QLineEdit(); executable.setReadOnly(True); executable.setPlaceholderText(self.EXECUTABLES[key]); form.addRow('Executável:',executable); status=QLabel('● Não configurado'); status.setStyleSheet('color:#999;font-weight:bold;'); form.addRow('Status:',status); layout.addWidget(installation)
        self.emulator_dir_edits[key]=directory; self.emulator_status_labels[key]=status; setattr(self,f'{key}_executable_edit',executable)
        if key=='mame':self._build_mame_content(layout)
        else:self._build_generic_content(layout,key,label)
        layout.addStretch(); scroll.setWidget(container); return scroll
    def _build_mame_content(self,layout:QVBoxLayout)->None:
        """Constrói a configuração de diretórios baseada no mame.ini real."""
        grp_ini=QGroupBox('mame.ini'); form_ini=QFormLayout(grp_ini); self.edit_ini_path=QLineEdit(); self.edit_ini_path.setReadOnly(True); self.edit_ini_path.setPlaceholderText('mame.ini não localizado'); btn=QPushButton('Selecionar…'); btn.clicked.connect(self._select_ini_file); row=QHBoxLayout(); row.addWidget(self.edit_ini_path,1); row.addWidget(btn); form_ini.addRow('Arquivo:',row); self.lbl_ini_status=QLabel('Não carregado'); form_ini.addRow('Status:',self.lbl_ini_status); load=QPushButton('Carregar mame.ini'); load.clicked.connect(self._load_ini); form_ini.addRow('',load); layout.addWidget(grp_ini)
        grp=QGroupBox('Diretórios definidos no mame.ini'); form=QFormLayout(grp); self.rom_paths=[]
        for i in range(1,6):
            edit=QLineEdit(); edit.setPlaceholderText(f'Diretório ROM {i}'); b=QPushButton('…'); b.setFixedWidth(34); b.clicked.connect(self._create_folder_selector(edit,f'Selecionar diretório ROM {i}')); row=QHBoxLayout(); row.addWidget(edit,1); row.addWidget(b); self.rom_paths.append(edit); form.addRow(f'ROM {i}:',row)
        self.dir_edits={}
        for label,attr,placeholder in [('Sample Path:','samplepath','samples'),('Artwork Path:','artpath','artwork'),('CFG Path:','cfgpath','cfg'),('NVRAM Path:','nvrampath','nvram'),('State Path:','statepath','sta'),('Snapshot Path:','snappath','snap'),('Diff Path:','diffpath','diff'),('INI Path:','inipath','ini')]:
            edit=QLineEdit(); edit.setPlaceholderText(placeholder); b=QPushButton('…'); b.setFixedWidth(34); b.clicked.connect(self._create_folder_selector(edit,f'Selecionar {label}')); row=QHBoxLayout(); row.addWidget(edit,1); row.addWidget(b); self.dir_edits[attr]=edit; form.addRow(label,row)
        save=QPushButton('Salvar mame.ini'); save.setStyleSheet('font-weight:bold;padding:8px;'); save.clicked.connect(self._save_ini); form.addRow('',save); layout.addWidget(grp); note=QLabel('O MAME usa o mame.ini como fonte de verdade. Os caminhos acima são lidos e gravados diretamente nesse arquivo.'); note.setWordWrap(True); note.setStyleSheet('color:#888;font-size:10px;'); layout.addWidget(note)
    def _build_generic_content(self,layout:QVBoxLayout,key:str,label:str)->None:
        """Constrói os diretórios de conteúdo do Flycast, Supermodel ou FBNeo."""
        group=QGroupBox(f'Diretórios de conteúdo do {label}'); form=QFormLayout(group); self.path_edits[key]={}
        for path_key,path_label in self.PATH_LABELS[key]:
            edit=QLineEdit(); edit.setPlaceholderText(path_label); b=QPushButton('…'); b.setFixedWidth(34); b.clicked.connect(self._create_emulator_path_selector(key,path_key,edit,path_label)); row=QHBoxLayout(); row.addWidget(edit,1); row.addWidget(b); self.path_edits[key][path_key]=edit; form.addRow(f'{path_label}:',row)
        save=QPushButton(f'Salvar diretórios do {label}'); save.setStyleSheet('font-weight:bold;padding:8px;'); save.clicked.connect(lambda _=False,k=key:self._save_generic_paths(k)); form.addRow('',save); layout.addWidget(group)
        notes={'flycast':'Os caminhos correspondem aos grupos de conteúdo usados pelo Flycast, como ContentPath, BiosPath, VMU, Save/State, Texture, Boxart e Cheats.','supermodel':'Supermodel usa ROMs MAME-compatíveis e possui Config, NVRAM, Saves e Assets na instalação. O caminho de ROMs é mantido pelo aplicativo para execução/catálogo.','fbneo':'FBNeo suporta múltiplos ROM paths e diversos support paths. Os campos representam os grupos usados pelo frontend e pelos serviços do projeto.'}; note=QLabel(notes[key]); note.setWordWrap(True); note.setStyleSheet('color:#888;font-size:10px;padding:4px;'); layout.addWidget(note)
    def _refresh_ui_state(self)->None:
        """Recarrega a configuração persistida e atualiza todas as subabas."""
        self.config.load()
        for key,_label in self.EMULATORS:
            directory=getattr(self.config,f'{key}_dir',None); self.emulator_dir_edits[key].setText(str(directory) if directory else ''); executable=Path(directory)/self.EXECUTABLES[key] if directory else None; getattr(self,f'{key}_executable_edit').setText(str(executable) if executable else ''); self._update_emulator_directory_status(key,directory)
            if key!='mame':self._load_generic_paths(key,directory)
        self._refresh_mame_from_config()
    def _update_emulator_directory_status(self,key:str,directory:Path|None)->None:
        """Mostra se o diretório e o executável esperado estão presentes."""
        status=self.emulator_status_labels[key]
        if not directory:status.setText('● Diretório não configurado');status.setStyleSheet('color:#999;font-weight:bold;');return
        executable=Path(directory)/self.EXECUTABLES[key]
        if executable.is_file():
            version=getattr(self.config,f'{key}_version',None); suffix=f' | versão {version}' if version else ''; status.setText(f'● Instalação detectada: {executable.name}{suffix}');status.setStyleSheet('color:#55d66b;font-weight:bold;')
        else:status.setText(f'● Diretório definido; {self.EXECUTABLES[key]} não localizado');status.setStyleSheet('color:#e5c454;font-weight:bold;')
    def _select_emulator_directory(self,key:str)->None:
        """Seleciona e persiste a raiz de instalação do emulador."""
        current=self.emulator_dir_edits[key].text().strip(); selected=QFileDialog.getExistingDirectory(self,f'Selecionar diretório do {dict(self.EMULATORS)[key]}',current)
        if not selected:return
        directory=Path(selected);setattr(self.config,f'{key}_dir',directory);executable=directory/self.EXECUTABLES[key];setattr(self.config,f'{key}_path',executable if executable.is_file() else None)
        if key!='mame':self._initialize_generic_defaults(key,directory)
        self.config.save();self.emulator_dir_edits[key].setText(str(directory));getattr(self,f'{key}_executable_edit').setText(str(executable));self._update_emulator_directory_status(key,directory)
        if key!='mame':self._load_generic_paths(key,directory)
        else:self._refresh_mame_from_config()
        self.settings_changed.emit()
    def _initialize_generic_defaults(self,key:str,directory:Path)->None:
        """Inicializa caminhos relativos à instalação sem sobrescrever configurações existentes."""
        for path_key,relative in self.config.EMULATOR_PATH_DEFAULTS.get(key,{}).items():
            if self.config.get_emulator_path(key,path_key) is None:self.config.set_emulator_path(key,path_key,directory/relative)
    def _load_generic_paths(self,key:str,directory:Path|None)->None:
        """Carrega os caminhos persistidos na subaba do emulador."""
        if key not in self.path_edits:return
        if directory:self._initialize_generic_defaults(key,directory)
        for path_key,edit in self.path_edits[key].items():
            path=self.config.get_emulator_path(key,path_key);edit.setText(str(path) if path else '')
    def _create_emulator_path_selector(self,key:str,path_key:str,edit_widget:QLineEdit,title:str):
        """Cria o callback para selecionar um diretório de conteúdo."""
        def selector()->None:
            current=edit_widget.text().strip();selected=QFileDialog.getExistingDirectory(self,f'Selecionar {title}',current)
            if selected:edit_widget.setText(selected);self.config.set_emulator_path(key,path_key,Path(selected))
        return selector
    def _save_generic_paths(self,key:str)->None:
        """Persiste todos os diretórios de conteúdo do emulador."""
        for path_key,edit in self.path_edits[key].items():
            value=edit.text().strip();self.config.set_emulator_path(key,path_key,Path(value) if value else None)
        self.config.save();self._update_emulator_directory_status(key,getattr(self.config,f'{key}_dir',None));self.settings_changed.emit();QMessageBox.information(self,dict(self.EMULATORS)[key],f'Diretórios do {dict(self.EMULATORS)[key]} salvos com sucesso.')
    def _refresh_mame_from_config(self)->None:
        """Atualiza o MAME a partir da instalação configurada."""
        mame_dir=self.config.mame_dir;mame_path=Path(mame_dir)/'mame.exe' if mame_dir else self.config.mame_path
        if mame_path and mame_path.is_file():self.config.mame_path=mame_path;self._detect_mame_version();self._load_default_mame_ini()
        else:self.mame_executable_edit.setText(str(mame_path) if mame_path else '');self.lbl_ini_status.setText('mame.ini não encontrado');self._set_ini_fields_enabled(False)
    def _select_mame_executable(self)->None:
        """Compatibilidade: seleção direta do MAME passa a selecionar sua pasta."""
        self._select_emulator_directory('mame')
    def _detect_mame_version(self)->None:
        """Detecta a versão do mame.exe instalado."""
        path=self.config.mame_path
        if not path or path.name.casefold()!='mame.exe' or not path.is_file():self.mame_executable_edit.setText(str(path) if path else '');return
        self.mame_executable_edit.setText(str(path))
        try:self.mame_exec=MameExecutable(path);version=self.mame_exec.version;self.config.mame_version=str(version);self.config.save();self._update_emulator_directory_status('mame',self.config.mame_dir)
        except Exception:self.emulator_status_labels['mame'].setText('● Erro na detecção da versão');self.emulator_status_labels['mame'].setStyleSheet('color:#e05a5a;font-weight:bold;')
    def _load_default_mame_ini(self)->None:
        """Carrega o mame.ini da raiz da instalação do MAME."""
        if not self.config.mame_dir:return
        path=Path(self.config.mame_dir)/'mame.ini'
        if path.is_file():self.config.ini_path=path;self.config.save();self.edit_ini_path.setText(str(path));self._load_ini()
        else:self.edit_ini_path.clear();self.lbl_ini_status.setText('mame.ini não encontrado na raiz do MAME');self.lbl_ini_status.setStyleSheet('color:#e5c454;font-weight:bold;');self._set_ini_fields_enabled(False)
    def _select_ini_file(self)->None:
        """Seleciona manualmente um mame.ini existente."""
        file_path,_=QFileDialog.getOpenFileName(self,'Selecionar mame.ini',str(self.config.mame_dir or ''),'Arquivos INI (*.ini);;Todos os arquivos (*)')
        if not file_path:return
        self.config.ini_path=Path(file_path);self.config.save();self.edit_ini_path.setText(file_path);self._load_ini()
    def _load_ini(self)->None:
        """Carrega o mame.ini e preenche os caminhos internos."""
        path=Path(self.edit_ini_path.text())
        if not path.is_file():self.lbl_ini_status.setText('mame.ini não encontrado');self._set_ini_fields_enabled(False);return
        try:self.ini_service=IniService(path);self._load_ini_values();self.lbl_ini_status.setText('● Carregado');self.lbl_ini_status.setStyleSheet('color:#55d66b;font-weight:bold;')
        except Exception as exc:self.ini_service=None;self.lbl_ini_status.setText(f'● Erro: {exc}');self.lbl_ini_status.setStyleSheet('color:#e05a5a;font-weight:bold;');self._set_ini_fields_enabled(False)
    def _load_ini_values(self)->None:
        """Preenche os campos com os caminhos encontrados no mame.ini."""
        if not self.ini_service:return
        rom_list=self.ini_service.get_paths('rompath')
        for i,edit in enumerate(self.rom_paths):edit.setText(rom_list[i] if i<len(rom_list) else '')
        mapping={'samplepath':self.ini_service.get_samplepath,'artpath':self.ini_service.get_artpath,'cfgpath':self.ini_service.get_cfgpath,'nvrampath':self.ini_service.get_nvrampath,'statepath':self.ini_service.get_statepath,'snappath':self.ini_service.get_snappath,'diffpath':self.ini_service.get_diffpath,'inipath':self.ini_service.get_inipath}
        for attr,getter in mapping.items():self.dir_edits[attr].setText(getter() or '')
        self._set_ini_fields_enabled(True)
    def _save_ini(self)->None:
        """Salva os caminhos alterados diretamente no mame.ini."""
        if not self.ini_service:QMessageBox.warning(self,'MAME','Nenhum mame.ini carregado para salvar.');return
        try:
            self.ini_service.set_paths('rompath',[edit.text().strip() for edit in self.rom_paths if edit.text().strip()])
            fields={'samplepath':self.dir_edits['samplepath'].text().strip(),'artpath':self.dir_edits['artpath'].text().strip(),'cfg_directory':self.dir_edits['cfgpath'].text().strip(),'nvram_directory':self.dir_edits['nvrampath'].text().strip(),'state_directory':self.dir_edits['statepath'].text().strip(),'snapshot_directory':self.dir_edits['snappath'].text().strip(),'diff_directory':self.dir_edits['diffpath'].text().strip(),'inipath':self.dir_edits['inipath'].text().strip()}
            for key,value in fields.items():self.ini_service.set(key,value)
            self.ini_service.save();self.config.ini_path=Path(self.edit_ini_path.text());self.config.save();self.settings_changed.emit();QMessageBox.information(self,'MAME','mame.ini salvo com sucesso.')
        except PermissionError:QMessageBox.critical(self,'MAME','Permissão negada para salvar o mame.ini.')
        except Exception as exc:QMessageBox.critical(self,'MAME',f'Falha ao salvar o mame.ini:\n{exc}')
    def _set_ini_fields_enabled(self,enabled:bool)->None:
        """Habilita ou desabilita os campos de diretórios do MAME."""
        for edit in self.rom_paths:edit.setEnabled(enabled)
        for edit in self.dir_edits.values():edit.setEnabled(enabled)
    def _create_folder_selector(self,edit_widget:QLineEdit,title:str):
        """Cria um seletor de pasta para um campo do MAME."""
        def selector()->None:
            selected=QFileDialog.getExistingDirectory(self,title,edit_widget.text())
            if selected:edit_widget.setText(selected)
        return selector
    def refresh(self)->None:
        """Atualiza as quatro subabas após alterações realizadas por outra interface."""
        self._refresh_ui_state()
