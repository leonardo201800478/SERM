from pathlib import Path

# ==========================================================
# DIRETÓRIO RAIZ DO PROJETO
# ==========================================================

ROOT = Path(__file__).resolve().parent

# ==========================================================
# PASTAS
# ==========================================================

DATA = ROOT / "data"

INPUT = DATA / "input"

OUTPUT = DATA / "output"

CACHE = DATA / "cache"

FOLDERS = INPUT / "folders"

LISTXML = INPUT / "listxml.xml"

# ==========================================================
# BANCO SQLITE
# ==========================================================

DATABASE = CACHE / "mame289.db"

# ==========================================================
# PASTAS DE SAÍDA
# ==========================================================

OUTPUT_XML = OUTPUT / "xml"

OUTPUT_DAT = OUTPUT / "dat"

OUTPUT_TXT = OUTPUT / "txt"

OUTPUT_CSV = OUTPUT / "csv"

OUTPUT_REPORT = OUTPUT / "reports"

# ==========================================================
# CRIAÇÃO AUTOMÁTICA DAS PASTAS
# ==========================================================

for folder in (
    DATA,
    INPUT,
    OUTPUT,
    CACHE,
    FOLDERS,
    OUTPUT_XML,
    OUTPUT_DAT,
    OUTPUT_TXT,
    OUTPUT_CSV,
    OUTPUT_REPORT,
):
    folder.mkdir(parents=True, exist_ok=True)