"""CLI principal da auditoria MAME/ListXML/Display Profile da V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..runtime.paths import data_root
from .mame_catalog_ingestor import MameCatalogIngestor
from .mame_catalog_report import MameCatalogReport


def configured_mame() -> Path:
    """Retorna o executável MAME selecionado na aba Diretórios."""
    path = data_root() / "emulator_paths.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("mame_executable")
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError("Nenhum mame_executable foi configurado em Diretórios.")
    return Path(raw).expanduser().resolve()


def main() -> int:
    """Executa a ingestão e imprime o relatório final de validação."""
    parser = argparse.ArgumentParser(
        description="Auditoria completa do catálogo/display MAME do SERM V2."
    )
    parser.add_argument("--mame", type=Path, help="Executável MAME; por padrão usa o configurado.")
    parser.add_argument("--resolution", type=Path, help="resolution.ini usado como fallback.")
    parser.add_argument("--vsync", type=Path, help="Vsync.ini usado como fallback.")
    parser.add_argument(
        "--force", action="store_true", help="Reprocessa um ListXML com o mesmo SHA."
    )
    args = parser.parse_args()

    executable = args.mame.resolve() if args.mame else configured_mame()
    result = MameCatalogIngestor().ingest(
        executable,
        resolution_ini=args.resolution,
        vsync_ini=args.vsync,
        force=args.force,
    )
    result["catalog_summary"] = MameCatalogReport().summary()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
