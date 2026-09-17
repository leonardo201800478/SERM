"""CLI for generating a controlled, read-only LaunchBox audit report."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ..integrations.launchbox_audit import LaunchBoxAudit
from ..runtime.paths import exports_root


def build_report(audit: LaunchBoxAudit, sample_limit: int) -> dict[str, object]:
    """Build a compact JSON-serializable audit report from external metadata."""
    tables = audit.tables()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "database": str(audit.provider.metadata_database()),
        "platforms_xml": str(audit.provider.platforms_xml()),
        "database_tables": [asdict(table) for table in tables],
        "platform_count": audit.platform_count(),
        "emulated_platform_count": audit.emulated_platform_count(),
        "game_sample": [asdict(game) for game in audit.game_sample(sample_limit)],
    }


def main(argv: list[str] | None = None) -> int:
    """Generate a LaunchBox audit JSON report and print its location."""
    parser = argparse.ArgumentParser(
        description="Audita a estrutura local do LaunchBox em modo somente leitura."
    )
    parser.add_argument(
        "--sample", type=int, default=10, help="Quantidade de jogos na amostra (padrão: 10)."
    )
    parser.add_argument(
        "--output", type=Path, help="Arquivo JSON de saída; por padrão usa v2/data/exports/."
    )
    args = parser.parse_args(argv)

    if args.sample < 1:
        parser.error("--sample deve ser maior que zero.")

    report = build_report(LaunchBoxAudit(), args.sample)
    output = args.output or exports_root() / "launchbox-audit.json"
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Relatório LaunchBox criado: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
