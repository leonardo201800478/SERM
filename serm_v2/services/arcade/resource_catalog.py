"""Catalogo declarativo de recursos externos do Arcade Studio."""

from __future__ import annotations

from collections.abc import Iterable

from ...models.external_resource import ExternalResource


class ExternalResourceCatalog:
    """Mantem recursos externos por identidade estavel.

    O catalogo e deliberadamente independente de HTTP e filesystem. Providers
    descobrem recursos; o catalogo apenas registra e compara suas identidades.
    """

    def __init__(self, resources: Iterable[ExternalResource] = ()) -> None:
        self._resources: dict[str, ExternalResource] = {}
        for resource in resources:
            self.add(resource)

    def add(self, resource: ExternalResource) -> None:
        """Adiciona ou substitui um recurso pela chave normalizada."""
        key = resource.normalized_id()
        self._resources[key] = resource

    def get(self, provider: str, platform: str, name: str, version: str) -> ExternalResource | None:
        """Localiza uma versao exata de um recurso."""
        key = ":".join(p.strip().casefold() for p in (provider, platform, name, version))
        return self._resources.get(key)

    def versions(self, provider: str, platform: str, name: str) -> list[str]:
        """Retorna versoes conhecidas de um recurso em ordem estavel."""
        prefix = ":".join(p.strip().casefold() for p in (provider, platform, name)) + ":"
        return sorted(
            resource.version
            for key, resource in self._resources.items()
            if key.startswith(prefix)
        )

    def all(self) -> tuple[ExternalResource, ...]:
        """Retorna todos os recursos em ordem deterministica."""
        return tuple(self._resources[key] for key in sorted(self._resources))

    def __len__(self) -> int:
        return len(self._resources)


__all__ = ["ExternalResourceCatalog"]
