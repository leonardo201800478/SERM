import tkinter as tk

class AdvancedFiltersTab:
    def __init__(self, parent, settings):
        self.parent = parent
        self.settings = settings

        self.frame = tk.Frame(self.parent)
        self.frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Variáveis
        self.remove_mechanical = tk.BooleanVar(value=self.settings.get('remove_mechanical', True))
        self.remove_bios = tk.BooleanVar(value=self.settings.get('remove_bios', True))
        self.remove_devices = tk.BooleanVar(value=self.settings.get('remove_devices', True))
        self.remove_junk = tk.BooleanVar(value=self.settings.get('remove_junk', True))
        self.keep_software_bios = tk.BooleanVar(value=self.settings.get('keep_software_bios', True))

        self.create_widgets()

    def create_widgets(self):
        frame = self.frame

        tk.Checkbutton(frame, text="Remover máquinas mecânicas (pinball, etc.)", variable=self.remove_mechanical).grid(row=0, column=0, sticky='w', pady=3)
        tk.Checkbutton(frame, text="Remover BIOS (exceto se mantido abaixo)", variable=self.remove_bios).grid(row=1, column=0, sticky='w', pady=3)
        tk.Checkbutton(frame, text="Remover Devices (periféricos, cartuchos, etc.)", variable=self.remove_devices).grid(row=2, column=0, sticky='w', pady=3)
        tk.Checkbutton(frame, text="Remover ROMs lixo (Bootlegs, Mahjong, Gambling, Quiz, Pachinko)", variable=self.remove_junk).grid(row=3, column=0, sticky='w', pady=3)

        tk.Label(frame, text=" ").grid(row=4, column=0, pady=5)

        tk.Checkbutton(frame, text="Manter BIOS de consoles domésticos e PCs (NES, SNES, Genesis, PSX, etc.)",
                       variable=self.keep_software_bios).grid(row=5, column=0, sticky='w', pady=3)

        tk.Label(frame, text="Se ativado, as BIOS de sistemas como NES, SNES, Mega Drive,\nPlayStation, N64, Game Boy, Master System, etc. serão PRESERVADAS,\nmesmo com a opção 'Remover BIOS' ativa.",
                 fg='gray', justify='left').grid(row=6, column=0, sticky='w', pady=10)

        tk.Label(frame, text="Dica: Desative 'Remover BIOS' se quiser manter TODAS as BIOS.",
                 fg='blue', justify='left').grid(row=7, column=0, sticky='w', pady=5)

    def get_values(self):
        return {
            'remove_mechanical': self.remove_mechanical.get(),
            'remove_bios': self.remove_bios.get(),
            'remove_devices': self.remove_devices.get(),
            'remove_junk': self.remove_junk.get(),
            'keep_software_bios': self.keep_software_bios.get(),
        }