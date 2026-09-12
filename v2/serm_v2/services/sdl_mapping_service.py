"""Parser da SDL_GameControllerDB usado como fonte de mapeamento.

A base comunitária não é tratada como cadastro mestre do SERM: ela apenas
fornece uma sugestão de normalização para um GUID conhecido.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SDLGamepadMapping:
    guid: str
    name: str
    bindings: dict[str, str]
    platform: str | None = None
    source: str = "SDL_GameControllerDB"


class SDLMappingService:
    """Lê o formato textual oficial usado pela SDL_GameControllerDB."""

    def load_file(self, path: str | Path) -> tuple[SDLGamepadMapping, ...]:
        mappings: list[SDLGamepadMapping] = []
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
            mapping = self.parse_line(line)
            if mapping is not None:
                mappings.append(mapping)
        return tuple(mappings)

    @staticmethod
    def parse_line(line: str) -> SDLGamepadMapping | None:
        text = line.strip()
        if not text or text.startswith("#"):
            return None
        fields = [field.strip() for field in text.split(",")]
        if len(fields) < 3 or not fields[0] or not fields[1]:
            return None

        guid, name = fields[0], fields[1]
        bindings: dict[str, str] = {}
        platform: str | None = None
        for field in fields[2:]:
            if not field or ":" not in field:
                continue
            key, value = field.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key == "platform":
                platform = value or None
            elif key:
                bindings[key] = value

        return SDLGamepadMapping(guid=guid.casefold(), name=name, bindings=bindings, platform=platform)

    def find_guid(self, mappings: tuple[SDLGamepadMapping, ...], guid: str) -> SDLGamepadMapping | None:
        normalized = guid.strip().casefold()
        for mapping in mappings:
            if mapping.guid == normalized:
                return mapping
        return None


__all__ = ["SDLGamepadMapping", "SDLMappingService"]
