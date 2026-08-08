import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import logging
from gui.tabs import PathsTab, BasicFiltersTab, AdvancedFiltersTab, TorrentsTab
from gui import settings_manager
from gui.processor import AsyncProcessor
import config
import main

# Configurar logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("MAME Set Builder - Configuração e Filtros")
        self.root.geometry("850x950")
        self.root.resizable(True, True)

        # Carregar configurações e atualizar config.MAME_EXE
        self.settings = settings_manager.load_settings()
        if 'mame_exe' in self.settings:
            config.MAME_EXE = Path(self.settings['mame_exe'])
            logger.debug(f"Config.MAME_EXE atualizado para: {config.MAME_EXE}")

        self.processor = None
        self.create_widgets()
        self.update_mame_version()

    def create_widgets(self):
        # Cabeçalho com versão do MAME
        header_frame = tk.Frame(self.root)
        header_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(header_frame, text="MAME Set Builder", font=('Arial', 16, 'bold')).pack(side='left')

        self.version_label = tk.Label(header_frame, text="Versão do MAME: não detectada", font=('Arial', 10), fg='blue')
        self.version_label.pack(side='right', padx=10)

        # Notebook
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)

        self.paths_tab = PathsTab(notebook, self.settings, self)
        notebook.add(self.paths_tab.frame, text="Caminhos")

        self.basic_tab = BasicFiltersTab(notebook, self.settings)
        notebook.add(self.basic_tab.frame, text="Filtros Básicos")

        self.advanced_tab = AdvancedFiltersTab(notebook, self.settings)
        notebook.add(self.advanced_tab.frame, text="Limpeza Avançada")

        self.torrents_tab = TorrentsTab(notebook, self.settings)
        notebook.add(self.torrents_tab.frame, text="Torrents")

        # Área de log
        log_frame = tk.Frame(self.root)
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.log_text = tk.Text(log_frame, height=12, state='disabled', wrap='word', font=('Consolas', 9))
        self.log_text.pack(fill='both', expand=True, side='left')
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # Barras de progresso
        progress_frame = tk.Frame(self.root)
        progress_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(progress_frame, text="Progresso Total:", font=('Arial', 9)).pack(anchor='w')
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill='x', pady=(0, 5))

        tk.Label(progress_frame, text="Progresso Parcial:", font=('Arial', 9)).pack(anchor='w')
        self.progress_partial_var = tk.DoubleVar()
        self.progress_partial_bar = ttk.Progressbar(progress_frame, variable=self.progress_partial_var, maximum=100)
        self.progress_partial_bar.pack(fill='x', pady=(0, 5))

        self.status_label = tk.Label(self.root, text="Pronto", font=('Arial', 9))
        self.status_label.pack(pady=5)

        # Botões
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        self.btn_save = tk.Button(btn_frame, text="Salvar Configuração", command=self.save_settings,
                                  bg='#2196F3', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5)
        self.btn_save.pack(side='left', padx=5)

        self.btn_import_xml = tk.Button(btn_frame, text="Importar XML", command=self.run_import_xml,
                                        bg='#FF9800', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5)
        self.btn_import_xml.pack(side='left', padx=5)

        self.btn_import_inis = tk.Button(btn_frame, text="Importar INIs", command=self.run_import_inis,
                                         bg='#9C27B0', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5)
        self.btn_import_inis.pack(side='left', padx=5)

        self.btn_generate = tk.Button(btn_frame, text="Gerar DAT", command=self.run_generate,
                                      bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'), padx=20, pady=8)
        self.btn_generate.pack(side='left', padx=5)

        self.btn_stop = tk.Button(btn_frame, text="⏹ Parar", command=self.stop_processing,
                                  bg='#F44336', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5)
        self.btn_stop.pack(side='left', padx=5)
        self.btn_stop.pack_forget()

    def update_mame_version(self):
        try:
            mame_path_str = self.paths_tab.mame_exe.get()
            if mame_path_str:
                mame_path = Path(mame_path_str)
                if mame_path.exists():
                    version = main.get_mame_version(mame_path)
                    if version:
                        self.version_label.config(text=f"Versão do MAME: {version}")
                        logger.info(f"Versão detectada: {version}")
                    else:
                        self.version_label.config(text="Versão do MAME: não detectada")
                        logger.warning("Versão não detectada")
                else:
                    self.version_label.config(text="MAME não encontrado")
                    logger.warning(f"Arquivo não encontrado: {mame_path}")
            else:
                self.version_label.config(text="MAME não configurado")
                logger.debug("Caminho do MAME vazio")
        except Exception as e:
            self.version_label.config(text="Erro ao obter versão")
            logger.error(f"Erro ao atualizar versão: {e}", exc_info=True)

    def log_message(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')
        self.root.update_idletasks()

    def update_progress(self, value=None, status="", partial_value=None):
        """
        Atualiza as barras de progresso e o status.
        - value: progresso total (0-100), se None não altera.
        - status: texto do status.
        - partial_value: progresso parcial (0-100), se None não altera.
        """
        if value is not None:
            self.progress_var.set(value)
        if partial_value is not None:
            self.progress_partial_var.set(partial_value)
        if status:
            self.status_label.config(text=status)
        self.root.update_idletasks()

    def save_settings(self):
        data = {}
        data.update(self.paths_tab.get_values())
        data.update(self.basic_tab.get_values())
        data.update(self.advanced_tab.get_values())
        data.update(self.torrents_tab.get_values())
        settings_manager.save_settings(data)
        self.update_mame_version()
        messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")

    def _update_config_from_gui(self):
        paths = self.paths_tab.get_values()
        basic = self.basic_tab.get_values()
        adv = self.advanced_tab.get_values()
        torrent = self.torrents_tab.get_values()

        config.MAME_EXE = Path(paths['mame_exe'])
        config.ROMS_DIR = Path(paths['roms_dir'])
        config.OUTPUT_DAT = Path(paths['output_dir']) / "filtrado.dat"
        config.FOLDERS = Path(paths['ini_folder']) if paths['ini_folder'] else Path("data/input/folders")
        config.DATABASE = Path(paths['db_file']) if paths['db_file'] else Path("data/cache/mame.db")

        config.FILTER_WORKING = basic['filter_working']
        config.FILTER_ARCADE = basic['filter_arcade']
        config.FILTER_CLONES = basic['filter_clones']
        config.FILTER_CONTROLS = basic['controls']
        config.FILTER_PLAYERS = basic['players']
        config.FILTER_CATEGORIES = basic['category']

        config.REMOVE_MECHANICAL = adv['remove_mechanical']
        config.REMOVE_BIOS = adv['remove_bios']
        config.REMOVE_DEVICES = adv['remove_devices']
        config.REMOVE_JUNK = adv['remove_junk']
        config.KEEP_SOFTWARE_BIOS = adv['keep_software_bios']

        config.TORRENT_LINKS = {
            "mame_roms": torrent['torrent_mame'],
            "mame_bios": torrent['torrent_bios'],
            "mame_chds": torrent['torrent_chds'],
            "software_roms": torrent['torrent_sw_roms'],
            "software_chds": torrent['torrent_sw_chds']
        }
        config.ENABLE_TORRENT = torrent['enable_torrent']
        config.ROM_DIR = Path(torrent['torrent_rom_dir']) if torrent['torrent_rom_dir'] else Path("roms")
        config.CHD_DIR = Path(torrent['torrent_chd_dir']) if torrent['torrent_chd_dir'] else Path("chds")
        config.SOFTWARE_ROM_DIR = Path(torrent['torrent_sw_rom_dir']) if torrent['torrent_sw_rom_dir'] else Path("software_roms")
        config.SOFTWARE_CHD_DIR = Path(torrent['torrent_sw_chd_dir']) if torrent['torrent_sw_chd_dir'] else Path("software_chds")

        config.QB_EXE = torrent.get('qb_exe', '')
        config.QB_HOST = torrent.get('qb_host', 'localhost')
        config.QB_PORT = torrent.get('qb_port', '8080')
        config.QB_USER = torrent.get('qb_user', 'admin')
        config.QB_PASS = torrent.get('qb_pass', 'adminadmin')

    def _run_async(self, target_func, description):
        paths = self.paths_tab.get_values()
        if not paths['mame_exe']:
            messagebox.showerror("Erro", "Selecione o executável do MAME.")
            return
        if not paths['roms_dir']:
            messagebox.showerror("Erro", "Selecione o diretório de ROMs.")
            return
        if not paths['output_dir']:
            messagebox.showerror("Erro", "Selecione o diretório de saída.")
            return

        self.save_settings()
        self._update_config_from_gui()

        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')
        self.update_progress(0, f"Iniciando {description}...", 0)

        for btn in [self.btn_save, self.btn_import_xml, self.btn_import_inis, self.btn_generate]:
            btn.config(state='disabled', bg='gray')
        self.btn_stop.pack(side='left', padx=5)

        self.processor = AsyncProcessor(
            target=target_func,
            log_callback=self.log_message,
            progress_callback=self.update_progress
        )
        self.processor.start()
        self.monitor_thread()

    def stop_processing(self):
        if self.processor and self.processor.is_alive():
            self.processor.stop()
            self.log_message("\n⏹ Parada solicitada... Aguardando término.")
            self.btn_stop.config(state='disabled', bg='gray')

    def monitor_thread(self):
        if self.processor and self.processor.is_alive():
            self.root.after(100, self.monitor_thread)
        else:
            for btn in [self.btn_save, self.btn_import_xml, self.btn_import_inis, self.btn_generate]:
                btn.config(state='normal', bg='#2196F3' if btn == self.btn_save else
                           '#FF9800' if btn == self.btn_import_xml else
                           '#9C27B0' if btn == self.btn_import_inis else
                           '#4CAF50')
            self.btn_stop.pack_forget()
            self.btn_stop.config(state='normal', bg='#F44336')
            self.progress_partial_var.set(0)

            if self.processor and self.processor.exception:
                self.log_message(f"\nERRO: {self.processor.exception}\n{self.processor.exception_traceback}")
                self.update_progress(0, "Erro", 0)
            else:
                self.log_message(f"\n{self.processor.result or 'Concluído com sucesso!'}")
                self.update_progress(100, "Concluído", 0)

    def run_import_xml(self):
        # Atualiza o config com os valores da GUI
        self._update_config_from_gui()

        # Obtém o caminho do executável diretamente da GUI
        mame_path_str = self.paths_tab.mame_exe.get()
        if not mame_path_str:
            messagebox.showerror("Erro", "Selecione o executável do MAME.")
            return

        mame_path = Path(mame_path_str)
        if not mame_path.exists():
            messagebox.showerror("Erro", f"Executável do MAME não encontrado em: {mame_path}")
            return

        # Obtém a versão do MAME usando o caminho explícito
        mame_ver = main.get_mame_version(mame_path)
        if mame_ver is None:
            messagebox.showerror("Erro", "Não foi possível obter a versão do MAME. Verifique o executável.")
            return

        # Obtém a versão do XML (se existir)
        xml_ver = main.get_xml_version()

        if not config.LISTXML.exists():
            if messagebox.askyesno("XML não encontrado", "O arquivo listxml.xml não existe. Deseja gerá-lo agora?"):
                status, msg = main.ensure_listxml(force=True)
                if status == 'error':
                    messagebox.showerror("Erro", msg)
                    return
                self._run_async(main.import_xml_only, "Importação do XML")
            return

        if xml_ver is None:
            if messagebox.askyesno("Versão desconhecida",
                                   f"O XML existente não tem versão identificada. A versão atual do MAME é {mame_ver}. Deseja atualizar?"):
                main.ensure_listxml(force=True)
                self._run_async(main.import_xml_only, "Importação do XML")
            else:
                messagebox.showinfo("Informação", "Mantendo o XML atual. Nenhuma importação será feita.")
            return

        if mame_ver == xml_ver:
            messagebox.showinfo("Versão compatível", f"XML já está na versão {mame_ver} do MAME. Prosseguindo com a importação.")
            self._run_async(main.import_xml_only, "Importação do XML")
        else:
            if messagebox.askyesno("Versão diferente",
                                   f"Versão do MAME ({mame_ver}) diferente da versão do XML ({xml_ver}). Deseja atualizar o XML?"):
                main.ensure_listxml(force=True)
                self._run_async(main.import_xml_only, "Importação do XML")
            else:
                messagebox.showinfo("Informação", "Mantendo o XML atual. Nenhuma importação será feita.")

    def run_import_inis(self):
        self._run_async(main.import_inis_only, "Importação dos INIs")

    def run_generate(self):
        self._run_async(main.generate_dat_only, "Geração do DAT")

if __name__ == "__main__":
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()