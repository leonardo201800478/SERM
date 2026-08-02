from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
CACHE_DIR = DATA_DIR / "cache"

MAME_EXE = Path("mame.exe")
ROMS_DIR = Path("roms")
LISTXML = INPUT_DIR / "listxml.xml"
FOLDERS = INPUT_DIR / "folders"
DATABASE = CACHE_DIR / "mame.db"
OUTPUT_DAT = OUTPUT_DIR / "filtrado.dat"

# Filtros básicos - agora são listas para múltipla escolha
FILTER_WORKING = True
FILTER_ARCADE = True
FILTER_CLONES = False          # False = excluir clones
FILTER_CONTROLS = []           # ex: ['joystick', 'trackball']
FILTER_PLAYERS = []            # ex: ['1', '2']
FILTER_CATEGORIES = []         # ex: ['Arcade', 'Console']

# Filtros avançados
REMOVE_MECHANICAL = True
REMOVE_BIOS = True
REMOVE_DEVICES = True
REMOVE_JUNK = True
KEEP_SOFTWARE_BIOS = True

# Torrents
TORRENT_LINKS = {
    "mame_roms": "",
    "mame_bios": "",
    "mame_chds": "",
    "software_roms": "",
    "software_chds": ""
}
ENABLE_TORRENT = True
ROM_DIR = Path("roms")
CHD_DIR = Path("chds")
SOFTWARE_ROM_DIR = Path("software_roms")
SOFTWARE_CHD_DIR = Path("software_chds")

# qBittorrent
QB_EXE = ""
QB_HOST = "localhost"
QB_PORT = "8080"
QB_USER = "admin"
QB_PASS = "adminadmin"