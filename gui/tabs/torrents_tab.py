import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path

class TorrentsTab:
    def __init__(self, notebook, settings):
        self.frame = ttk.Frame(notebook)
        self.settings = settings
        self.create_widgets()

    def create_widgets(self):
        frame = self.frame
        row = 0

        tk.Label(frame, text="Links Magnéticos para cada categoria:", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=3, sticky='w', pady=10)
        row += 1

        tk.Label(frame, text="MAME ROMs:").grid(row=row, column=0, sticky='w', pady=3)
        self.torrent_mame = tk.StringVar(value=self.settings.get('torrent_mame', ''))
        tk.Entry(frame, textvariable=self.torrent_mame, width=80).grid(row=row, column=1, padx=5)
        row += 1

        tk.Label(frame, text="BIOS/Devices:").grid(row=row, column=0, sticky='w', pady=3)
        self.torrent_bios = tk.StringVar(value=self.settings.get('torrent_bios', ''))
        tk.Entry(frame, textvariable=self.torrent_bios, width=80).grid(row=row, column=1, padx=5)
        row += 1

        tk.Label(frame, text="MAME CHDs:").grid(row=row, column=0, sticky='w', pady=3)
        self.torrent_chds = tk.StringVar(value=self.settings.get('torrent_chds', ''))
        tk.Entry(frame, textvariable=self.torrent_chds, width=80).grid(row=row, column=1, padx=5)
        row += 1

        tk.Label(frame, text="Software List ROMs:").grid(row=row, column=0, sticky='w', pady=3)
        self.torrent_sw_roms = tk.StringVar(value=self.settings.get('torrent_sw_roms', ''))
        tk.Entry(frame, textvariable=self.torrent_sw_roms, width=80).grid(row=row, column=1, padx=5)
        row += 1

        tk.Label(frame, text="Software List CHDs:").grid(row=row, column=0, sticky='w', pady=3)
        self.torrent_sw_chds = tk.StringVar(value=self.settings.get('torrent_sw_chds', ''))
        tk.Entry(frame, textvariable=self.torrent_sw_chds, width=80).grid(row=row, column=1, padx=5)
        row += 1

        # Seção qBittorrent
        tk.Label(frame, text="Configuração do qBittorrent", font=('Arial', 10, 'bold')).grid(row=row, column=0, columnspan=3, sticky='w', pady=15)
        row += 1

        tk.Label(frame, text="Executável qBittorrent:").grid(row=row, column=0, sticky='w')
        self.qb_exe = tk.StringVar(value=self.settings.get('qb_exe', ''))
        tk.Entry(frame, textvariable=self.qb_exe, width=50).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_qb).grid(row=row, column=2)
        row += 1

        tk.Label(frame, text="Host (ex: localhost):").grid(row=row, column=0, sticky='w')
        self.qb_host = tk.StringVar(value=self.settings.get('qb_host', 'localhost'))
        tk.Entry(frame, textvariable=self.qb_host, width=30).grid(row=row, column=1, sticky='w')
        row += 1

        tk.Label(frame, text="Porta (ex: 8080):").grid(row=row, column=0, sticky='w')
        self.qb_port = tk.StringVar(value=self.settings.get('qb_port', '8080'))
        tk.Entry(frame, textvariable=self.qb_port, width=30).grid(row=row, column=1, sticky='w')
        row += 1

        tk.Label(frame, text="Usuário:").grid(row=row, column=0, sticky='w')
        self.qb_user = tk.StringVar(value=self.settings.get('qb_user', 'admin'))
        tk.Entry(frame, textvariable=self.qb_user, width=30).grid(row=row, column=1, sticky='w')
        row += 1

        tk.Label(frame, text="Senha:").grid(row=row, column=0, sticky='w')
        self.qb_pass = tk.StringVar(value=self.settings.get('qb_pass', 'adminadmin'))
        tk.Entry(frame, textvariable=self.qb_pass, width=30, show='*').grid(row=row, column=1, sticky='w')
        row += 1

        self.enable_torrent = tk.BooleanVar(value=self.settings.get('enable_torrent', True))
        tk.Checkbutton(frame, text="Gerar script de download para arquivos faltantes", variable=self.enable_torrent).grid(row=row, column=0, columnspan=2, sticky='w', pady=10)
        row += 1

        # Diretórios
        tk.Label(frame, text="Diretório de ROMs (para verificação):").grid(row=row, column=0, sticky='w', pady=3)
        self.torrent_rom_dir = tk.StringVar(value=self.settings.get('torrent_rom_dir', 'roms'))
        tk.Entry(frame, textvariable=self.torrent_rom_dir, width=50).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_rom).grid(row=row, column=2)
        row += 1

        tk.Label(frame, text="Diretório de CHDs:").grid(row=row, column=0, sticky='w', pady=3)
        self.torrent_chd_dir = tk.StringVar(value=self.settings.get('torrent_chd_dir', 'chds'))
        tk.Entry(frame, textvariable=self.torrent_chd_dir, width=50).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_chd).grid(row=row, column=2)
        row += 1

        tk.Label(frame, text="Software ROMs dir:").grid(row=row, column=0, sticky='w', pady=3)
        self.torrent_sw_rom_dir = tk.StringVar(value=self.settings.get('torrent_sw_rom_dir', 'software_roms'))
        tk.Entry(frame, textvariable=self.torrent_sw_rom_dir, width=50).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_sw_rom).grid(row=row, column=2)
        row += 1

        tk.Label(frame, text="Software CHDs dir:").grid(row=row, column=0, sticky='w', pady=3)
        self.torrent_sw_chd_dir = tk.StringVar(value=self.settings.get('torrent_sw_chd_dir', 'software_chds'))
        tk.Entry(frame, textvariable=self.torrent_sw_chd_dir, width=50).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_sw_chd).grid(row=row, column=2)
        row += 1

    def browse_qb(self):
        f = filedialog.askopenfilename(title="Selecione o executável do qBittorrent", filetypes=[("Executáveis", "*.exe")])
        if f: self.qb_exe.set(f)

    def browse_rom(self):
        d = filedialog.askdirectory(title="Selecione o diretório de ROMs")
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
            'qb_exe': self.qb_exe.get(),
            'qb_host': self.qb_host.get(),
            'qb_port': self.qb_port.get(),
            'qb_user': self.qb_user.get(),
            'qb_pass': self.qb_pass.get(),
            'torrent_rom_dir': self.torrent_rom_dir.get(),
            'torrent_chd_dir': self.torrent_chd_dir.get(),
            'torrent_sw_rom_dir': self.torrent_sw_rom_dir.get(),
            'torrent_sw_chd_dir': self.torrent_sw_chd_dir.get()
        }