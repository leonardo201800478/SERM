import tkinter as tk
from tkinter import filedialog
from pathlib import Path

class PathsTab:
    def __init__(self, parent, settings, main_window=None):
        self.parent = parent
        self.main_window = main_window
        self.settings = settings

        self.frame = tk.Frame(self.parent)
        self.frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.mame_exe = tk.StringVar(value=self.settings.get('mame_exe', ''))
        self.roms_dir = tk.StringVar(value=self.settings.get('roms_dir', ''))
        self.output_dir = tk.StringVar(value=self.settings.get('output_dir', ''))
        self.ini_folder = tk.StringVar(value=self.settings.get('ini_folder', 'data/input/folders'))
        self.db_file = tk.StringVar(value=self.settings.get('db_file', 'data/cache/mame.db'))

        self.create_widgets()

    def create_widgets(self):
        frame = self.frame
        row = 0

        tk.Label(frame, text="MAME Executável:", anchor='w').grid(row=row, column=0, sticky='w', pady=5)
        entry_mame = tk.Entry(frame, textvariable=self.mame_exe, width=60)
        entry_mame.grid(row=row, column=1, padx=5)
        # Quando o usuário alterar o caminho, atualiza versão
        entry_mame.bind('<KeyRelease>', self.on_mame_path_change)
        tk.Button(frame, text="Procurar...", command=self.browse_mame).grid(row=row, column=2)
        row += 1

        tk.Label(frame, text="Diretório de ROMs:", anchor='w').grid(row=row, column=0, sticky='w', pady=5)
        tk.Entry(frame, textvariable=self.roms_dir, width=60).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_roms).grid(row=row, column=2)
        row += 1

        tk.Label(frame, text="Diretório de Saída:", anchor='w').grid(row=row, column=0, sticky='w', pady=5)
        tk.Entry(frame, textvariable=self.output_dir, width=60).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_output).grid(row=row, column=2)
        row += 1

        tk.Label(frame, text="Pasta de INIs (catver, controls, players...):", anchor='w').grid(row=row, column=0, sticky='w', pady=5)
        tk.Entry(frame, textvariable=self.ini_folder, width=60).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_ini).grid(row=row, column=2)
        row += 1

        tk.Label(frame, text="Banco de Dados (automático):", anchor='w').grid(row=row, column=0, sticky='w', pady=5)
        tk.Entry(frame, textvariable=self.db_file, width=60, state='readonly').grid(row=row, column=1, padx=5)
        row += 1

        tk.Label(frame, text="O listxml será gerado automaticamente a partir do MAME.", fg='gray').grid(row=row, column=0, columnspan=3, sticky='w', pady=10)

    def on_mame_path_change(self, event=None):
        """Callback quando o caminho do MAME é alterado."""
        if self.main_window:
            self.main_window.update_mame_version()

    def browse_mame(self):
        f = filedialog.askopenfilename(title="Selecione o executável do MAME", filetypes=[("Executáveis", "*.exe"), ("Todos", "*.*")])
        if f:
            self.mame_exe.set(f)
            self.on_mame_path_change()

    def browse_roms(self):
        d = filedialog.askdirectory(title="Selecione o diretório de ROMs")
        if d: self.roms_dir.set(d)

    def browse_output(self):
        d = filedialog.askdirectory(title="Selecione o diretório de saída")
        if d: self.output_dir.set(d)

    def browse_ini(self):
        d = filedialog.askdirectory(title="Selecione a pasta com arquivos .ini")
        if d: self.ini_folder.set(d)

    def get_values(self):
        return {
            'mame_exe': self.mame_exe.get(),
            'roms_dir': self.roms_dir.get(),
            'output_dir': self.output_dir.get(),
            'ini_folder': self.ini_folder.get(),
            'db_file': self.db_file.get(),
        }