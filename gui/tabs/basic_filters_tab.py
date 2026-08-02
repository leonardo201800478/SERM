import tkinter as tk
from tkinter import ttk

class BasicFiltersTab:
    def __init__(self, parent, settings):
        self.parent = parent
        self.settings = settings

        self.frame = tk.Frame(self.parent)
        self.frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Variáveis
        self.filter_working = tk.BooleanVar(value=self.settings.get('filter_working', True))
        self.filter_arcade = tk.BooleanVar(value=self.settings.get('filter_arcade', True))
        self.filter_clones = tk.BooleanVar(value=self.settings.get('filter_clones', False))
        self.control_type = tk.StringVar(value=self.settings.get('control_type', ''))
        self.players = tk.StringVar(value=self.settings.get('players', ''))
        self.category = tk.StringVar(value=self.settings.get('category', ''))

        self.control_options = ['', 'joystick', 'trackball', 'lightgun', 'paddle', 'spinner', 'keyboard', 'mouse']
        self.player_options = ['', '1', '2', '3', '4', '8']
        self.category_options = ['', 'Arcade', 'Console', 'Computer', 'Other']

        self.create_widgets()

    def create_widgets(self):
        frame = self.frame

        tk.Checkbutton(frame, text="Apenas máquinas funcionando (working)", variable=self.filter_working).grid(row=0, column=0, sticky='w', pady=3)
        tk.Checkbutton(frame, text="Apenas Arcade (category contém 'Arcade')", variable=self.filter_arcade).grid(row=1, column=0, sticky='w', pady=3)
        tk.Checkbutton(frame, text="Excluir clones (apenas pais)", variable=self.filter_clones, onvalue=False, offvalue=True).grid(row=2, column=0, sticky='w', pady=3)

        # Controles
        tk.Label(frame, text="Tipo de Controle:").grid(row=0, column=1, padx=30, sticky='w')
        ttk.Combobox(frame, textvariable=self.control_type, values=self.control_options, width=15).grid(row=0, column=2, sticky='w')

        tk.Label(frame, text="Nº de Jogadores:").grid(row=1, column=1, padx=30, sticky='w')
        ttk.Combobox(frame, textvariable=self.players, values=self.player_options, width=15).grid(row=1, column=2, sticky='w')

        tk.Label(frame, text="Categoria (catver):").grid(row=2, column=1, padx=30, sticky='w')
        ttk.Combobox(frame, textvariable=self.category, values=self.category_options, width=15).grid(row=2, column=2, sticky='w')

        tk.Label(frame, text="Nota: Controle, Jogadores e Categoria dependem dos .ini.", fg='gray').grid(row=3, column=0, columnspan=3, sticky='w', pady=20)

    def get_values(self):
        return {
            'filter_working': self.filter_working.get(),
            'filter_arcade': self.filter_arcade.get(),
            'filter_clones': self.filter_clones.get(),
            'control_type': self.control_type.get(),
            'players': self.players.get(),
            'category': self.category.get(),
        }