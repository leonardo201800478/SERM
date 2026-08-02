import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
import config

class TorrentsTab:
    def __init__(self, parent, settings):
        self.parent = parent
        self.settings = settings

        self.frame = tk.Frame(self.parent)
        self.frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Variáveis
        self.torrent_mame = tk.StringVar(value=self.settings.get('torrent_mame', ''))
        self.torrent_bios = tk.StringVar(value=self.settings.get('torrent_bios', ''))
        self.torrent_chds = tk.StringVar(value=self.settings.get('torrent_chds', ''))
        self.torrent_sw_roms = tk.StringVar(value=self.settings.get('torrent_sw_roms', ''))
        self.torrent_sw_chds = tk.StringVar(value=self.settings.get('torrent_sw_chds', ''))
        self.enable_torrent = tk.BooleanVar(value=self.settings.get('enable_torrent', True))
        self.torrent_rom_dir = tk.StringVar(value=self.settings.get('torrent_rom_dir', str(config.ROM_DIR)))
        self.torrent_chd_dir = tk.StringVar(value=self.settings.get('torrent_chd_dir', str(config.CHD_DIR)))
        self.torrent_sw_rom_dir = tk.StringVar(value=self.settings.get('torrent_sw_rom_dir', str(config.SOFTWARE_ROM_DIR)))
        self.torrent_sw_chd_dir = tk.StringVar(value=self.settings.get('torrent_sw_chd_dir', str(config.SOFTWARE_CHD_DIR)))

        self.create_widgets()

    def create_widgets(self):
        frame = self.frame
        row = 0

        tk.Label(frame, text="Links Magnéticos para cada categoria:", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=3, sticky='w', pady=10)
        row += 1

        tk.Label(frame, text="MAME ROMs:").grid(row=row, column=0, sticky='w', pady=3)
        tk.Entry(frame, textvariable=self.torrent_mame, width=80).grid(row=row, column=1, padx=5)
        row += 1

        tk.Label(frame, text="BIOS/Devices:").grid(row=row, column=0, sticky='w', pady=3)
        tk.Entry(frame, textvariable=self.torrent_bios, width=80).grid(row=row, column=1, padx=5)
        row += 1

        tk.Label(frame, text="MAME CHDs:").grid(row=row, column=0, sticky='w', pady=3)
        tk.Entry(frame, textvariable=self.torrent_chds, width=80).grid(row=row, column=1, padx=5)
        row += 1

        tk.Label(frame, text="Software List ROMs:").grid(row=row, column=0, sticky='w', pady=3)
        tk.Entry(frame, textvariable=self.torrent_sw_roms, width=80).grid(row=row, column=1, padx=5)
        row += 1

        tk.Label(frame, text="Software List CHDs:").grid(row=row, column=0, sticky='w', pady=3)
        tk.Entry(frame, textvariable=self.torrent_sw_chds, width=80).grid(row=row, column=1, padx=5)
        row += 1

        tk.Checkbutton(frame, text="Gerar script de download para arquivos faltantes", variable=self.enable_torrent).grid(row=row, column=0, columnspan=2, sticky='w', pady=10)
        row += 1

        tk.Label(frame, text="Diretório de ROMs (para verificação):").grid(row=row, column=0, sticky='w', pady=3)
        tk.Entry(frame, textvariable=self.torrent_rom_dir, width=60).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_rom).grid(row=row, column=2)
        row += 1

        tk.Label(frame, text="Diretório de CHDs:").grid(row=row, column=0, sticky='w', pady=3)
        tk.Entry(frame, textvariable=self.torrent_chd_dir, width=60).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_chd).grid(row=row, column=2)
        row += 1

        tk.Label(frame, text="Software ROMs dir:").grid(row=row, column=0, sticky='w', pady=3)
        tk.Entry(frame, textvariable=self.torrent_sw_rom_dir, width=60).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_sw_rom).grid(row=row, column=2)
        row += 1

        tk.Label(frame, text="Software CHDs dir:").grid(row=row, column=0, sticky='w', pady=3)
        tk.Entry(frame, textvariable=self.torrent_sw_chd_dir, width=60).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_sw_chd).grid(row=row, column=2)
        row += 1

    def browse_rom(self):
        d = filedialog.askdirectory(title="Selecione o diretório de ROMs (para verificação)")
        if d: self.torrent_rom_dir.set(d)

    def browse_chd(self):
        d = filedialog.askdirectory(title="Selecione o diretório de CHDs")
        if d: self.torrent_chd_dir.set(d)

    def browse_sw_rom(self):
        d = filedialog.askdirectory(title="Selecione o diretório de Software ROMs")
        if d: self.torrent_sw_rom_dir.set(d)

    def browse_sw_chd(self):
        d = filedialog.askdirectory(title="Selecione o diretório de Software CHDs")
        if d: self.torrent_sw_chd_dir.set(d)

    def get_values(self):
        return {
            'torrent_mame': self.torrent_mame.get(),
            'torrent_bios': self.torrent_bios.get(),
            'torrent_chds': self.torrent_chds.get(),
            'torrent_sw_roms': self.torrent_sw_roms.get(),
            'torrent_sw_chds': self.torrent_sw_chds.get(),
            'enable_torrent': self.enable_torrent.get(),
            'torrent_rom_dir': self.torrent_rom_dir.get(),
            'torrent_chd_dir': self.torrent_chd_dir.get(),
            'torrent_sw_rom_dir': self.torrent_sw_rom_dir.get(),
            'torrent_sw_chd_dir': self.torrent_sw_chd_dir.get(),
        }