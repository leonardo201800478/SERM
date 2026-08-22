"""Layer-2 resolver connecting configuration schema to runtime capability data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capabilities import EmulatorCapabilities, get_capabilities
from .config_schema import Setting, get_schema
from .runtime import RuntimeCapabilities, discover_all


@dataclass(frozen=True, slots=True)
class ResolvedSetting:
    """Layer-2 setting contract consumed directly by Layer-3 widgets."""

    setting: Setting
    available: bool
    reason: str | None = None


class ConfigResolver:
    """Resolve schema settings without changing the Layer-1 contract."""

    def __init__(self, runtime: dict[str, RuntimeCapabilities] | None = None) -> None:
        self.runtime = runtime if runtime is not None else discover_all()

    def capabilities(self, emulator: str) -> EmulatorCapabilities:
        """Return static capabilities for an emulator."""
        return get_capabilities(emulator.strip().lower())

    def runtime_capabilities(self, emulator: str) -> RuntimeCapabilities:
        """Return detected runtime capabilities for an emulator."""
        key = emulator.strip().lower()
        try:
            return self.runtime[key]
        except KeyError as exc:
            raise ValueError(f"Emulador não suportado: {emulator}") from exc

    def settings(self, emulator: str, domain: str) -> tuple[ResolvedSetting, ...]:
        """Annotate every schema setting with static/runtime availability."""
        key = emulator.strip().lower()
        schema = get_schema(key)
        static = self.capabilities(key)
        runtime = self.runtime_capabilities(key)
        try:
            items = schema[domain]
        except KeyError as exc:
            raise ValueError(f"Domínio não suportado: {key}/{domain}") from exc

        resolved: list[ResolvedSetting] = []
        for setting in items:
            if setting.feature is not None and not static.supports(setting.feature):
                resolved.append(ResolvedSetting(setting, False, "Recurso não faz parte deste emulador."))
                continue
            if setting.feature is not None and runtime.available and not runtime.supports(setting.feature):
                resolved.append(ResolvedSetting(setting, False, "Recurso não está disponível nesta instalação."))
                continue
            if not runtime.available:
                resolved.append(ResolvedSetting(setting, False, "Executável não detectado."))
                continue
            resolved.append(ResolvedSetting(setting, True))
        return tuple(resolved)

    def visible_settings(self, emulator: str, domain: str) -> tuple[Setting, ...]:
        """Return only controls that are currently editable."""
        return tuple(item.setting for item in self.settings(emulator, domain) if item.available)

    def defaults(self, emulator: str, domain: str) -> dict[str, Any]:
        """Return defaults for the controls currently exposed by Layer 2."""
        return {item.key: item.default for item in self.visible_settings(emulator, domain)}
