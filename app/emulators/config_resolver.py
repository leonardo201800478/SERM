"""Layer-2 resolver for configuration options.

It combines the stable Layer-1 schema with runtime capabilities. GUI builders
can therefore request only settings that the detected executable can expose.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capabilities import EmulatorCapabilities, get_capabilities
from .config_schema import Setting, get_schema
from .runtime import RuntimeCapabilities, discover_all


@dataclass(frozen=True, slots=True)
class ResolvedSetting:
    """A schema setting annotated with its runtime availability."""

    setting: Setting
    available: bool
    reason: str | None = None


class ConfigResolver:
    """Resolves Layer-1 settings against Layer-2 runtime capabilities."""

    def __init__(self, runtime: dict[str, RuntimeCapabilities] | None = None) -> None:
        self.runtime = runtime if runtime is not None else discover_all()

    def capabilities(self, emulator: str) -> EmulatorCapabilities:
        """Return static capabilities for an emulator."""
        return get_capabilities(emulator)

    def runtime_capabilities(self, emulator: str) -> RuntimeCapabilities:
        """Return detected capabilities for an emulator."""
        key = emulator.strip().lower()
        try:
            return self.runtime[key]
        except KeyError as exc:
            raise ValueError(f"Emulador não suportado: {emulator}") from exc

    def settings(self, emulator: str, domain: str) -> tuple[ResolvedSetting, ...]:
        """Resolve every setting in a domain without silently dropping it."""
        schema = get_schema(emulator)
        static = self.capabilities(emulator)
        runtime = self.runtime_capabilities(emulator)
        try:
            items = schema[domain]
        except KeyError as exc:
            raise ValueError(f"Domínio não suportado: {emulator}/{domain}") from exc

        resolved: list[ResolvedSetting] = []
        for setting in items:
            if setting.feature is None:
                resolved.append(ResolvedSetting(setting, True))
                continue
            if not static.supports(setting.feature):
                resolved.append(ResolvedSetting(setting, False, "Recurso não faz parte deste emulador."))
                continue
            if runtime.available and not runtime.supports(setting.feature):
                resolved.append(ResolvedSetting(setting, False, "Recurso não está disponível nesta instalação."))
                continue
            resolved.append(ResolvedSetting(setting, runtime.available, "Executável não detectado." if not runtime.available else None))
        return tuple(resolved)

    def visible_settings(self, emulator: str, domain: str) -> tuple[Setting, ...]:
        """Return only settings currently safe to expose as editable controls."""
        return tuple(item.setting for item in self.settings(emulator, domain) if item.available)

    def defaults(self, emulator: str, domain: str) -> dict[str, Any]:
        """Return default values for all visible settings in a domain."""
        return {item.key: item.default for item in self.visible_settings(emulator, domain)}
