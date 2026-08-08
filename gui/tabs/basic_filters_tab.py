import tkinter as tk
from tkinter import ttk

class BasicFiltersTab:
    def __init__(self, notebook, settings):
        self.frame = ttk.Frame(notebook)
        self.settings = settings
        self.create_widgets()

    def create_widgets(self):
        main_frame = tk.Frame(self.frame, padx=10, pady=10)
        main_frame.pack(fill='both', expand=True)

        # Checkboxes principais
        top_frame = tk.Frame(main_frame)
        top_frame.pack(fill='x', pady=(0, 10))

        self.filter_working = tk.BooleanVar(value=self.settings.get('filter_working', True))
        self.filter_arcade = tk.BooleanVar(value=self.settings.get('filter_arcade', True))
        self.filter_clones = tk.BooleanVar(value=self.settings.get('filter_clones', False))

        tk.Checkbutton(top_frame, text="Apenas máquinas funcionando (working)", variable=self.filter_working).pack(side='left', padx=(0, 20))
        tk.Checkbutton(top_frame, text="Apenas Arcade (category contém 'Arcade')", variable=self.filter_arcade).pack(side='left', padx=(0, 20))
        tk.Checkbutton(top_frame, text="Excluir clones (apenas pais)", variable=self.filter_clones, onvalue=False, offvalue=True).pack(side='left')

        # Controles
        ctrl_group = tk.LabelFrame(main_frame, text="Tipos de Controle (selecione um ou mais)", font=('Arial', 10, 'bold'))
        ctrl_group.pack(fill='x', pady=5)

        ctrl_frame = tk.Frame(ctrl_group)
        ctrl_frame.pack(padx=10, pady=5)

        control_options = ['joystick', 'trackball', 'lightgun', 'paddle', 'spinner', 'keyboard', 'mouse', 'dial', 'pedal']
        self.control_vars = {}
        row, col = 0, 0
        for opt in control_options:
            var = tk.BooleanVar(value=self.settings.get(f'control_{opt}', False))
            self.control_vars[opt] = var
            cb = tk.Checkbutton(ctrl_frame, text=opt.capitalize(), variable=var)
            cb.grid(row=row, column=col, sticky='w', padx=5, pady=2)
            col += 1
            if col >= 5:
                col = 0
                row += 1

        btn_ctrl_frame = tk.Frame(ctrl_group)
        btn_ctrl_frame.pack(pady=5)
        tk.Button(btn_ctrl_frame, text="Selecionar todos", command=self.select_all_controls, font=('Arial', 8), width=15).pack(side='left', padx=5)
        tk.Button(btn_ctrl_frame, text="Limpar todos", command=self.clear_all_controls, font=('Arial', 8), width=15).pack(side='left', padx=5)

        # Jogadores
        players_group = tk.LabelFrame(main_frame, text="Nº de Jogadores (selecione um ou mais)", font=('Arial', 10, 'bold'))
        players_group.pack(fill='x', pady=5)

        players_frame = tk.Frame(players_group)
        players_frame.pack(padx=10, pady=5)

        player_options = ['1', '2', '3', '4', '8']
        self.player_vars = {}
        for idx, opt in enumerate(player_options):
            var = tk.BooleanVar(value=self.settings.get(f'players_{opt}', False))
            self.player_vars[opt] = var
            cb = tk.Checkbutton(players_frame, text=f"{opt} jogador{'es' if int(opt)>1 else ''}", variable=var)
            cb.grid(row=0, column=idx, padx=10, sticky='w')

        btn_players_frame = tk.Frame(players_group)
        btn_players_frame.pack(pady=5)
        tk.Button(btn_players_frame, text="Selecionar todos", command=self.select_all_players, font=('Arial', 8), width=15).pack(side='left', padx=5)
        tk.Button(btn_players_frame, text="Limpar todos", command=self.clear_all_players, font=('Arial', 8), width=15).pack(side='left', padx=5)

        # Categorias
        cat_group = tk.LabelFrame(main_frame, text="Categorias (selecione uma ou mais)", font=('Arial', 10, 'bold'))
        cat_group.pack(fill='x', pady=5)

        cat_frame = tk.Frame(cat_group)
        cat_frame.pack(padx=10, pady=5)

        category_options = ['Arcade', 'Console', 'Computer', 'Other']
        self.category_vars = {}
        for idx, opt in enumerate(category_options):
            var = tk.BooleanVar(value=self.settings.get(f'category_{opt}', False))
            self.category_vars[opt] = var
            cb = tk.Checkbutton(cat_frame, text=opt, variable=var)
            cb.grid(row=0, column=idx, padx=10, sticky='w')

        btn_cat_frame = tk.Frame(cat_group)
        btn_cat_frame.pack(pady=5)
        tk.Button(btn_cat_frame, text="Selecionar todos", command=self.select_all_categories, font=('Arial', 8), width=15).pack(side='left', padx=5)
        tk.Button(btn_cat_frame, text="Limpar todos", command=self.clear_all_categories, font=('Arial', 8), width=15).pack(side='left', padx=5)

        tk.Label(main_frame, text="Nota: Controle, Jogadores e Categoria dependem dos arquivos .ini.", fg='gray', font=('Arial', 9)).pack(pady=(10,0), anchor='w')

    def select_all_controls(self):
        for var in self.control_vars.values():
            var.set(True)

    def clear_all_controls(self):
        for var in self.control_vars.values():
            var.set(False)

    def select_all_players(self):
        for var in self.player_vars.values():
            var.set(True)

    def clear_all_players(self):
        for var in self.player_vars.values():
            var.set(False)

    def select_all_categories(self):
        for var in self.category_vars.values():
            var.set(True)

    def clear_all_categories(self):
        for var in self.category_vars.values():
            var.set(False)

    def get_values(self):
        values = {
            'filter_working': self.filter_working.get(),
            'filter_arcade': self.filter_arcade.get(),
            'filter_clones': self.filter_clones.get(),
            'controls': [k for k, v in self.control_vars.items() if v.get()],
            'players': [k for k, v in self.player_vars.items() if v.get()],
            'category': [k for k, v in self.category_vars.items() if v.get()]
        }
        # Flags individuais para persistência
        for opt, var in self.control_vars.items():
            values[f'control_{opt}'] = var.get()
        for opt, var in self.player_vars.items():
            values[f'players_{opt}'] = var.get()
        for opt, var in self.category_vars.items():
            values[f'category_{opt}'] = var.get()
        return values