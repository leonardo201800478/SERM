import tkinter as tk
from tkinter import filedialog
from pathlib import Path

class PathsTab:
    def __init__(self, parent, settings, main_window=None):
        """
        Aba de configuração de caminhos.
        
        Args:
            parent: widget pai (o notebook)
            settings: dicionário com configurações carregadas
            main_window: referência à janela principal (opcional)
        """
        self.parent = parent
        self.main_window = main_window
        self.settings = settings

        # Criar o frame que será adicionado ao notebook
        self.frame = tk.Frame(self.parent)
        self.frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Variáveis dos campos
        self.mame_exe = tk.StringVar(value=self.settings.get('mame_exe', ''))
        self.roms_dir = tk.StringVar(value=self.settings.get('roms_dir', ''))
        self.output_dir = tk.StringVar(value=self.settings.get('output_dir', ''))
        self.ini_folder = tk.StringVar(value=self.settings.get('ini_folder', 'data/input/folders'))
        self.db_file = tk.StringVar(value=self.settings.get('db_file', 'data/cache/mame.db'))

        self.create_widgets()

    def create_widgets(self):
        frame = self.frame
        row = 0

        # MAME Executável
        tk.Label(frame, text="MAME Executável:", anchor='w').grid(row=row, column=0, sticky='w', pady=5)
        tk.Entry(frame, textvariable=self.mame_exe, width=60).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_mame).grid(row=row, column=2)
        row += 1

        # Diretório de ROMs
        tk.Label(frame, text="Diretório de ROMs:", anchor='w').grid(row=row, column=0, sticky='w', pady=5)
        tk.Entry(frame, textvariable=self.roms_dir, width=60).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_roms).grid(row=row, column=2)
        row += 1

        # Diretório de Saída
        tk.Label(frame, text="Diretório de Saída:", anchor='w').grid(row=row, column=0, sticky='w', pady=5)
        tk.Entry(frame, textvariable=self.output_dir, width=60).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_output).grid(row=row, column=2)
        row += 1

        # Pasta de INIs
        tk.Label(frame, text="Pasta de INIs (catver, controls, players...):", anchor='w').grid(row=row, column=0, sticky='w', pady=5)
        tk.Entry(frame, textvariable=self.ini_folder, width=60).grid(row=row, column=1, padx=5)
        tk.Button(frame, text="Procurar...", command=self.browse_ini).grid(row=row, column=2)
        row += 1

        # Banco de Dados (apenas leitura, gerado automaticamente)
        tk.Label(frame, text="Banco de Dados (automático):", anchor='w').grid(row=row, column=0, sticky='w', pady=5)
        tk.Entry(frame, textvariable=self.db_file, width=60, state='readonly').grid(row=row, column=1, padx=5)
        row += 1

        # Informação sobre o listxml
        tk.Label(frame, text="O listxml será gerado automaticamente a partir do MAME.", fg='gray').grid(
            row=row, column=0, columnspan=3, sticky='w', pady=10
        )

    # --- Métodos de navegação ---
    def browse_mame(self):
        f = filedialog.askopenfilename(
            title="Selecione o executável do MAME",
            filetypes=[("Executáveis", "*.exe"), ("Todos", "*.*")]
        )
        if f:
            self.mame_exe.set(f)

    def browse_roms(self):
        d = filedialog.askdirectory(title="Selecione o diretório de ROMs")
        if d:
            self.roms_dir.set(d)

    def browse_output(self):
        d = filedialog.askdirectory(title="Selecione o diretório de saída")
        if d:
            self.output_dir.set(d)

    def browse_ini(self):
        d = filedialog.askdirectory(title="Selecione a pasta com arquivos .ini")
        if d:
            self.ini_folder.set(d)

    def get_values(self):
        """Retorna um dicionário com todos os valores atuais dos campos."""
        return {
            'mame_exe': self.mame_exe.get(),
            'roms_dir': self.roms_dir.get(),
            'output_dir': self.output_dir.get(),
            'ini_folder': self.ini_folder.get(),
            'db_file': self.db_file.get(),
        }