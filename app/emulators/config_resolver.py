"""Layer 2: resolve o Schema × Adapter contra o runtime detectado."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapter_registry import EmulatorAdapterSpec, get_adapter
from .capabilities import EmulatorCapabilities
from .config_schema import Setting
from .runtime import RuntimeCapabilities, discover_all


@dataclass(frozen=True, slots=True)
class ResolvedSetting:
    """Contrato final de um controle disponível para a camada GUI."""

    setting: Setting
    available: bool
    reason: str | None = None


class ConfigResolver:
    """Resolve schema, adapter e runtime sem expor detalhes físicos à GUI."""

    def __init__(self, runtime: dict[str, RuntimeCapabilities] | None = None) -> None:
        self.runtime = runtime if runtime is not None else discover_all()

    def adapter(self, emulator: str) -> EmulatorAdapterSpec:
        """Retorna o contrato consolidado do emulador."""
        return get_adapter(emulator)

    def capabilities(self, emulator: str) -> EmulatorCapabilities:
        """Retorna capabilities estáticas através do adapter central."""
        return self.adapter(emulator).capabilities

    def runtime_capabilities(self, emulator: str) -> RuntimeCapabilities:
        """Retorna capabilities descobertas para o emulador."""
        key = emulator.strip().lower()
        try:
            return self.runtime[key]
        except KeyError as exc:
            raise ValueError(f"Emulador não suportado: {emulator}") from exc

    def settings(self, emulator: str, domain: str) -> tuple[ResolvedSetting, ...]:
        """Combina schema canônico, capabilities e estado real da instalação."""
        adapter = self.adapter(emulator)
        runtime = self.runtime_capabilities(adapter.emulator)
        items = adapter.schema(domain)
        resolved: list[ResolvedSetting] = []
        for setting in items:
            if setting.feature is not None and not adapter.capabilities.supports(setting.feature):
                resolved.append(ResolvedSetting(setting, False, "Recurso não declarado pelo adapter."))
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
        """Retorna apenas controles editáveis no runtime atual."""
        return tuple(item.setting for item in self.settings(emulator, domain) if item.available)

    def defaults(self, emulator: str, domain: str) -> dict[str, Any]:
        """Retorna defaults do schema para os controles visíveis."""
        return {item.key: item.default for item in self.visible_settings(emulator, domain)}
