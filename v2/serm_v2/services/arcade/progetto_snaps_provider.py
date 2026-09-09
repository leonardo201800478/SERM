"""Provider isolado para recursos MAME publicados pelo Progetto-SNAPS.

A descoberta web fica concentrada aqui. O restante do SERM recebe apenas
``ExternalResource`` e nao conhece URLs, nomes de ZIP ou layout do site.
"""

from __future__ import annotations

from ...models.external_resource import (
    ExternalResource,
    ExternalResourceType,
    ExtractionMode,
    ResourceStorage,
)
from .resource_catalog import ExternalResourceCatalog


class ProgettoSnapsProvider:
    """Catalogo declarativo inicial dos recursos suportados pelo SERM."""

    provider = "progetto_snaps"
    base_url = "https://www.progettosnaps.net"
    samples_url = f"{base_url}/samples/"

    def resources(self, version: str = "0.289") -> tuple[ExternalResource, ...]:
        """Retorna recursos MAME conhecidos para uma versao.

        Metadados sao armazenados no SERM; samples permanecem como recurso
        fisico da origem MAME. Os arquivos de classificacao devem ser
        descobertos pelo conteudo do pacote durante a etapa de ingestao, e nao
        por nomes de ZIP codificados no restante da aplicacao.
        """
        resources = [
            self._metadata("catver", version, "pS_CatVer_289.zip" if version == "0.289" else None),
            self._metadata("series", version, "pS_Series_289.zip" if version == "0.289" else None),
            self._metadata("languages", version, "pS_Languages_289.zip" if version == "0.289" else None),
            self._metadata("gameinit", version, "pS_gameinit_289.zip" if version == "0.289" else None),
            self._metadata("command", version, "pS_Command_273.zip" if version == "0.273" else None),
            self._metadata("bestgames", version, "pS_BestGames_280.zip" if version == "0.280" else None),
        ]
        resources.append(
            ExternalResource(
                resource_id="mame-samples-fullpack",
                provider=self.provider,
                platform="mame",
                name="samples-fullpack",
                version="0.289",
                resource_type=ExternalResourceType.SAMPLE,
                url=f"{self.base_url}/samples/packs/MAME_samples_289.zip",
                storage=ResourceStorage.MAME_SOURCE,
                extraction=ExtractionMode.ARCHIVE,
                required=False,
                notes="FullPack oficial/unofficial de samples 0.289; validar conteudo antes de publicar.",
                metadata={"listing_url": self.samples_url},
            )
        )
        return tuple(resource for resource in resources if resource is not None)

    def catalog(self, version: str = "0.289") -> ExternalResourceCatalog:
        """Constroi um catalogo pronto para consulta."""
        return ExternalResourceCatalog(self.resources(version))

    def _metadata(self, name: str, version: str, filename: str | None) -> ExternalResource | None:
        if filename is None:
            return None
        return ExternalResource(
            resource_id=f"mame-{name}",
            provider=self.provider,
            platform="mame",
            name=name,
            version=version,
            resource_type=ExternalResourceType.METADATA,
            url=f"{self.base_url}/support/",
            storage=ResourceStorage.SERM_METADATA,
            extraction=ExtractionMode.ARCHIVE,
            required=False,
            notes=f"Pacote de referencia: {filename}. Descoberta de membros deve usar o manifesto do pacote.",
            metadata={"package_filename": filename},
        )


__all__ = ["ProgettoSnapsProvider"]
