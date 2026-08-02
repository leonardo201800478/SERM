import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from gui.tabs import PathsTab, BasicFiltersTab, AdvancedFiltersTab, TorrentsTab
from gui import settings_manager
import config
import main

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("MAME Set Builder - Configuração e Filtros")
        self.root.geometry("780x750")
        self.root.resizable(False, False)

        self.settings = settings_manager.load_settings()
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self.root, text="MAME Set Builder - Configuração", font=('Arial', 16, 'bold')).pack(pady=10)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)

        self.paths_tab = PathsTab(notebook, self.settings, self)
        notebook.add(self.paths_tab.frame, text="Caminhos")   # <-- .frame

        self.basic_tab = BasicFiltersTab(notebook, self.settings)
        notebook.add(self.basic_tab.frame, text="Filtros Básicos")

        self.advanced_tab = AdvancedFiltersTab(notebook, self.settings)
        notebook.add(self.advanced_tab.frame, text="Limpeza Avançada")

        self.torrents_tab = TorrentsTab(notebook, self.settings)
        notebook.add(self.torrents_tab.frame, text="Torrents")

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=15)

        tk.Button(btn_frame, text="Salvar Configuração", command=self.save_settings,
                  bg='#2196F3', fg='white', font=('Arial', 10, 'bold'), padx=15, pady=5).pack(side='left', padx=10)
        tk.Button(btn_frame, text="Executar", command=self.run,
                  bg='#4CAF50', fg='white', font=('Arial', 12, 'bold'), padx=20, pady=8).pack(side='left', padx=10)

    def save_settings(self):
        data = {}
        data.update(self.paths_tab.get_values())
        data.update(self.basic_tab.get_values())
        data.update(self.advanced_tab.get_values())
        data.update(self.torrents_tab.get_values())
        settings_manager.save_settings(data)
        messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")

    def run(self):
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

        config.MAME_EXE = Path(paths['mame_exe'])
        config.ROMS_DIR = Path(paths['roms_dir'])
        config.OUTPUT_DAT = Path(paths['output_dir']) / "filtrado.dat"
        config.FOLDERS = Path(paths['ini_folder']) if paths['ini_folder'] else Path("data/input/folders")
        config.DATABASE = Path(paths['db_file']) if paths['db_file'] else Path("data/cache/mame.db")

        basic = self.basic_tab.get_values()
        config.FILTER_WORKING = basic['filter_working']
        config.FILTER_ARCADE = basic['filter_arcade']
        config.FILTER_CLONES = basic['filter_clones']
        config.FILTER_CONTROL = basic['control_type']
        config.FILTER_PLAYERS = basic['players']
        config.FILTER_CATEGORY = basic['category']

        adv = self.advanced_tab.get_values()
        config.REMOVE_MECHANICAL = adv['remove_mechanical']
        config.REMOVE_BIOS = adv['remove_bios']
        config.REMOVE_DEVICES = adv['remove_devices']
        config.REMOVE_JUNK = adv['remove_junk']
        config.KEEP_SOFTWARE_BIOS = adv['keep_software_bios']

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

        self.root.destroy()
        main.main()

if __name__ == "__main__":
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()