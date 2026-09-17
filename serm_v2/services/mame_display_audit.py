"""CLI para executar a auditoria completa do display MAME."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..runtime.paths import data_root
from .mame_display_pipeline import MameDisplayPipeline


def configured_mame_executable() -> Path:
    """Lê o mame_executable salvo pela aba Diretórios."""
    import json as _json

    path_file = data_root() / "emulator_paths.json"
    data = _json.loads(path_file.read_text(encoding="utf-8"))
    raw = data.get("mame_executable")
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError("Nenhum mame_executable configurado em Diretórios.")
    return Path(raw).expanduser().resolve()


def main() -> int:
    """Executa ListXML → comparação → Machine Display Profile e imprime JSON."""
    parser = argparse.ArgumentParser(description="Audita display/timing do MAME no SERM V2.")
    parser.add_argument("--mame", type=Path, help="Executável MAME; por padrão usa Diretórios.")
    parser.add_argument("--resolution", type=Path, help="Arquivo resolution.ini.")
    parser.add_argument("--vsync", type=Path, help="Arquivo Vsync.ini.")
    parser.add_argument(
        "--force", action="store_true", help="Reimporta mesmo quando o SHA do XML já existe."
    )
    args = parser.parse_args()

    executable = args.mame.resolve() if args.mame else configured_mame_executable()
    result = MameDisplayPipeline().run(
        executable,
        resolution_ini=args.resolution,
        vsync_ini=args.vsync,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
