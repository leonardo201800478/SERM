"""CLI for quantitative LaunchBox content auditing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..integrations.launchbox_content_audit import LaunchBoxContentAudit
from ..integrations.launchbox_provider import LaunchBoxProvider
from ..runtime.paths import exports_root


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Audit the content population of LaunchBox metadata.")
    parser.add_argument(
        "--output",
        type=Path,
        default=exports_root() / "launchbox-content-audit.json",
        help="JSON output path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the quantitative LaunchBox audit and write its JSON report."""
    args = build_parser().parse_args(argv)
    report = LaunchBoxContentAudit(LaunchBoxProvider()).summary()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Auditoria de conteúdo LaunchBox criada: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
