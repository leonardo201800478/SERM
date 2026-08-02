import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from gui.tabs import PathsTab, BasicFiltersTab, AdvancedFiltersTab, TorrentsTab
from gui import settings_manager
from gui.processor import AsyncProcessor
import config
import main

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("MAME Set Builder - Configuração e Filtros")
        self.root.geometry("800x800")
        self.root.resizable(True, True)

        self.settings = settings_manager.load_settings()
        self.processor = None
        self.create_widgets()

    def create_widgets(self):
        # Título
        tk.Label(self.root, text="MAME Set Builder - Configuração", font=('Arial', 16, 'bold')).pack(pady=10)

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

        # Área de log e progresso
        log_frame = tk.Frame(self.root)
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.log_text = tk.Text(log_frame, height=12, state='disabled', wrap='word', font=('Consolas', 9))
        self.log_text.pack(fill='both', expand=True, side='left')

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # Barra de progresso
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill='x', padx=10, pady=5)

        self.status_label = tk.Label(self.root, text="Pronto", font=('Arial', 9))
        self.status_label.pack(pady=5)

        # Botões
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        self.btn_save = tk.Button(btn_frame, text="Salvar Configuração", command=self.save_settings,
                                  bg='#2196F3', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5)
        self.btn_save.pack(side='left', padx=10)

        self.btn_run = tk.Button(btn_frame, text="Executar", command=self.run,
                                 bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'), padx=20, pady=8)
        self.btn_run.pack(side='left', padx=10)

    def log_message(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')
        self.root.update_idletasks()

    def update_progress(self, value, status=""):
        self.progress_var.set(value)
        self.status_label.config(text=status)
        self.root.update_idletasks()

    def save_settings(self):
        data = {}
        data.update(self.paths_tab.get_values())
        data.update(self.basic_tab.get_values())
        data.update(self.advanced_tab.get_values())
        data.update(self.torrents_tab.get_values())
        settings_manager.save_settings(data)
        messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")

    def run(self):
        # Validar campos
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

        # Salvar configurações
        self.save_settings()

        # Atualizar config
        config.MAME_EXE = Path(paths['mame_exe'])
        config.ROMS_DIR = Path(paths['roms_dir'])
        config.OUTPUT_DAT = Path(paths['output_dir']) / "filtrado.dat"
        config.FOLDERS = Path(paths['ini_folder']) if paths['ini_folder'] else Path("data/input/folders")
        config.DATABASE = Path(paths['db_file']) if paths['db_file'] else Path("data/cache/mame.db")

        # Filtros básicos
        basic = self.basic_tab.get_values()
        config.FILTER_WORKING = basic['filter_working']
        config.FILTER_ARCADE = basic['filter_arcade']
        config.FILTER_CLONES = basic['filter_clones']
        config.FILTER_CONTROL = basic['control_type']
        config.FILTER_PLAYERS = basic['players']
        config.FILTER_CATEGORY = basic['category']

        # Filtros avançados
        adv = self.advanced_tab.get_values()
        config.REMOVE_MECHANICAL = adv['remove_mechanical']
        config.REMOVE_BIOS = adv['remove_bios']
        config.REMOVE_DEVICES = adv['remove_devices']
        config.REMOVE_JUNK = adv['remove_junk']
        config.KEEP_SOFTWARE_BIOS = adv['keep_software_bios']

        # Torrents
        torrent = self.torrents_tab.get_values()
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

        # Configurações do qBittorrent
        config.QB_EXE = torrent.get('qb_exe', '')
        config.QB_HOST = torrent.get('qb_host', 'localhost')
        config.QB_PORT = torrent.get('qb_port', '8080')
        config.QB_USER = torrent.get('qb_user', 'admin')
        config.QB_PASS = torrent.get('qb_pass', 'adminadmin')

        # Limpar log e progresso
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')
        self.update_progress(0, "Iniciando...")

        # Desabilitar botões
        self.btn_run.config(state='disabled', bg='gray')
        self.btn_save.config(state='disabled', bg='gray')

        # Executar em thread
        self.processor = AsyncProcessor(
            target=main.main,
            log_callback=self.log_message,
            progress_callback=self.update_progress
        )
        self.processor.start()

        # Monitorar término
        self.monitor_thread()

    def monitor_thread(self):
        if self.processor and self.processor.is_alive():
            self.root.after(100, self.monitor_thread)
        else:
            # Reabilitar botões
            self.btn_run.config(state='normal', bg='#4CAF50')
            self.btn_save.config(state='normal', bg='#2196F3')
            if self.processor and self.processor.exception:
                self.log_message(f"\nERRO: {self.processor.exception}\n{self.processor.exception_traceback}")
                self.update_progress(0, "Erro")
            else:
                self.log_message("\nProcessamento concluído com sucesso!")
                self.update_progress(100, "Concluído")

if __name__ == "__main__":
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()