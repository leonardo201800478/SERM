"""Conservative parser for No-Intro filename metadata."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath


@dataclass(frozen=True, slots=True)
class NoIntroNameInfo:
    """Metadata explicitly encoded in a No-Intro filename."""

    title: str
    region: str | None = None
    languages: tuple[str, ...] = ()
    version: str | None = None
    development_status: str | None = None
    additional: tuple[str, ...] = ()
    special: tuple[str, ...] = ()
    license: str | None = None
    status: str | None = None


_TOKEN_RE = re.compile(r"\s*\(([^()]*)\)")


def parse_name(filename: str) -> NoIntroNameInfo:
    """Parse filename tokens conservatively without changing the source name."""
    stem = PurePath(filename).stem
    tokens = _TOKEN_RE.findall(stem)
    title = _TOKEN_RE.split(stem, maxsplit=1)[0].strip()
    if not tokens:
        return NoIntroNameInfo(title=title)

    region = tokens[0]
    languages: tuple[str, ...] = ()
    version = None
    development_status = None
    additional: list[str] = []
    special: list[str] = []
    license_name = None
    status = None

    for token in tokens[1:]:
        if token in {"Beta", "Proto", "Demo", "Sample", "Pre-release"}:
            development_status = token
        elif token.startswith(("Rev ", "v", "Version ")):
            version = token
        elif token.startswith("[") and token.endswith("]"):
            status = token
        elif token in {"Alt", "Unl", "Pirate", "Aftermarket"}:
            additional.append(token)
        elif token in {"Special Edition", "Limited Edition"}:
            special.append(token)
        elif token in {"Licensed", "Unlicensed"}:
            license_name = token
        elif re.fullmatch(r"[A-Za-z]{2}(?:-[A-Za-z]{2})?(?:,[A-Za-z]{2}(?:-[A-Za-z]{2})?)*", token):
            languages = tuple(token.split(","))
        else:
            additional.append(token)

    return NoIntroNameInfo(
        title=title,
        region=region,
        languages=languages,
        version=version,
        development_status=development_status,
        additional=tuple(additional),
        special=tuple(special),
        license=license_name,
        status=status,
    )
