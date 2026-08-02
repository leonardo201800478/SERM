import tkinter as tk
from tkinter import ttk

class BasicFiltersTab:
    def __init__(self, notebook, settings):
        self.frame = ttk.Frame(notebook)
        self.settings = settings
        self.create_widgets()

    def create_widgets(self):
        frame = self.frame
        row = 0

        # --- Checkboxes principais ---
        self.filter_working = tk.BooleanVar(value=self.settings.get('filter_working', True))
        self.filter_arcade = tk.BooleanVar(value=self.settings.get('filter_arcade', True))
        self.filter_clones = tk.BooleanVar(value=self.settings.get('filter_clones', False))  # False = excluir clones

        tk.Checkbutton(frame, text="Apenas máquinas funcionando (working)", variable=self.filter_working).grid(row=row, column=0, sticky='w', pady=2)
        row += 1
        tk.Checkbutton(frame, text="Apenas Arcade (category contém 'Arcade')", variable=self.filter_arcade).grid(row=row, column=0, sticky='w', pady=2)
        row += 1
        tk.Checkbutton(frame, text="Excluir clones (apenas pais)", variable=self.filter_clones, onvalue=False, offvalue=True).grid(row=row, column=0, sticky='w', pady=2)
        row += 1

        # --- Controles (múltipla escolha) ---
        tk.Label(frame, text="Tipos de Controle (selecione um ou mais):", font=('Arial', 9, 'bold')).grid(row=row, column=0, sticky='w', pady=(10,0))
        row += 1

        control_options = ['joystick', 'trackball', 'lightgun', 'paddle', 'spinner', 'keyboard', 'mouse', 'dial', 'pedal']
        self.control_vars = {}
        controls_frame = tk.Frame(frame)
        controls_frame.grid(row=row, column=0, columnspan=3, sticky='w')
        col = 0
        for opt in control_options:
            var = tk.BooleanVar(value=self.settings.get(f'control_{opt}', False))
            self.control_vars[opt] = var
            cb = tk.Checkbutton(controls_frame, text=opt.capitalize(), variable=var)
            cb.grid(row=0, column=col, sticky='w', padx=5)
            col += 1
        row += 1

        # --- Número de Jogadores (múltipla escolha) ---
        tk.Label(frame, text="Nº de Jogadores (selecione um ou mais):", font=('Arial', 9, 'bold')).grid(row=row, column=0, sticky='w', pady=(10,0))
        row += 1

        player_options = ['1', '2', '3', '4', '8']
        self.player_vars = {}
        players_frame = tk.Frame(frame)
        players_frame.grid(row=row, column=0, columnspan=3, sticky='w')
        col = 0
        for opt in player_options:
            var = tk.BooleanVar(value=self.settings.get(f'players_{opt}', False))
            self.player_vars[opt] = var
            cb = tk.Checkbutton(players_frame, text=f"{opt} jogador{'es' if int(opt)>1 else ''}", variable=var)
            cb.grid(row=0, column=col, sticky='w', padx=5)
            col += 1
        row += 1

        # --- Categoria (catver) (múltipla escolha) ---
        tk.Label(frame, text="Categorias (selecione uma ou mais):", font=('Arial', 9, 'bold')).grid(row=row, column=0, sticky='w', pady=(10,0))
        row += 1

        category_options = ['Arcade', 'Console', 'Computer', 'Other']
        self.category_vars = {}
        cat_frame = tk.Frame(frame)
        cat_frame.grid(row=row, column=0, columnspan=3, sticky='w')
        col = 0
        for opt in category_options:
            var = tk.BooleanVar(value=self.settings.get(f'category_{opt}', False))
            self.category_vars[opt] = var
            cb = tk.Checkbutton(cat_frame, text=opt, variable=var)
            cb.grid(row=0, column=col, sticky='w', padx=5)
            col += 1
        row += 1

        # Nota
        tk.Label(frame, text="Nota: Controle, Jogadores e Categoria dependem dos .ini.", fg='gray').grid(row=row, column=0, columnspan=3, sticky='w', pady=20)

    def get_values(self):
        controls = [k for k, v in self.control_vars.items() if v.get()]
        players = [k for k, v in self.player_vars.items() if v.get()]
        categories = [k for k, v in self.category_vars.items() if v.get()]

        return {
            'filter_working': self.filter_working.get(),
            'filter_arcade': self.filter_arcade.get(),
            'filter_clones': self.filter_clones.get(),
            'controls': controls,
            'players': players,
            'category': categories
        }