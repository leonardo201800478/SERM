"""SERM V2 application package."""

__version__ = "2.0.0-dev"

# Correções de compatibilidade da Home/RetroArch carregadas uma única vez na
# inicialização do pacote. A implementação principal continua em services/.
from .services import retroarch_home_fix as _retroarch_home_fix  # noqa: F401,E402
