from pathlib import Path

# Diretórios base
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
CACHE_DIR = DATA_DIR / "cache"

# Caminhos (serão sobrescritos pela GUI)
MAME_EXE = Path("mame.exe")
ROMS_DIR = Path("roms")
LISTXML = INPUT_DIR / "listxml.xml"
FOLDERS = INPUT_DIR / "folders"
DATABASE = CACHE_DIR / "mame.db"
OUTPUT_DAT = OUTPUT_DIR / "filtrado.dat"

# Filtros básicos (GUI - Aba 1)
FILTER_WORKING = True
FILTER_ARCADE = True
FILTER_CLONES = False   # False = excluir clones
FILTER_CONTROL = ""
FILTER_PLAYERS = ""
FILTER_CATEGORY = ""

# Filtros avançados de limpeza (GUI - Aba 2)
REMOVE_MECHANICAL = True
REMOVE_BIOS = True
REMOVE_DEVICES = True
REMOVE_JUNK = True       # Bootlegs, Mahjong, Gambling, Quiz, Pachinko
KEEP_SOFTWARE_BIOS = True  # Mantém BIOS de consoles/PCs (NES, SNES, Genesis, etc.)

# ... (configurações anteriores permanecem)

# === LINKS MAGNÉTICOS PARA TORRENTS ===
TORRENT_LINKS = {
    "mame_roms": "",          # Link magnético para MAME ROMs
    "mame_bios": "",          # Link magnético para BIOS/Devices
    "mame_chds": "",          # Link magnético para CHDs
    "software_roms": "",      # Link magnético para Software List ROMs
    "software_chds": ""       # Link magnético para Software List CHDs
}

# Diretórios para verificação (podem ser os mesmos de ROMs)
ROM_DIR = Path("roms")
CHD_DIR = Path("chds")
SOFTWARE_ROM_DIR = Path("software_roms")
SOFTWARE_CHD_DIR = Path("software_chds")


# === LINKS MAGNÉTICOS PARA TORRENTS ===
TORRENT_LINKS = {
    "mame_roms": "",
    "mame_bios": "",
    "mame_chds": "",
    "software_roms": "",
    "software_chds": ""
}
ENABLE_TORRENT = True

# Diretórios para verificação de arquivos
ROM_DIR = Path("roms")
CHD_DIR = Path("chds")
SOFTWARE_ROM_DIR = Path("software_roms")
SOFTWARE_CHD_DIR = Path("software_chds")
