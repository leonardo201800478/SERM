"""Allow SERM V2 to be started with ``python -m serm_v2``."""
from __future__ import annotations

from .main import main


if __name__ == "__main__":
    raise SystemExit(main())
