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
    """Catalogo declarativo dos recursos MAME relevantes ao SERM."""

    provider = "progetto_snaps"
    base_url = "https://www.progettosnaps.net"
    samples_url = f"{base_url}/samples/"
    support_url = f"{base_url}/support/"

    _METADATA = (
        ("catver", "0.289", "/catver/", "CatVer.ini"),
        ("series", "0.289", "/series/", "Series.ini"),
        ("languages", "0.289", "/languages/", "Languages.ini"),
        ("gameinit", "0.289", "/gameinit/", "GameInit.dat"),
        ("bestgames", "0.280", "/bestgames/", "BestGames.ini"),
        ("command", "0.273", "/command/", "Command.dat"),
    )

    def resources(self) -> tuple[ExternalResource, ...]:
        """Retorna os recursos atualmente publicados, independentemente da versao MAME."""
        resources = [
            self._metadata(name, version, page, filename)
            for name, version, page, filename in self._METADATA
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
                notes="FullPack MAME Samples 0.289; validar conteudo antes de publicar.",
                metadata={"listing_url": self.samples_url, "package_count": 75},
            )
        )
        return tuple(resources)

    def catalog(self) -> ExternalResourceCatalog:
        """Constroi um catalogo pronto para consulta."""
        return ExternalResourceCatalog(self.resources())

    def _metadata(
        self,
        name: str,
        version: str,
        page: str,
        filename: str,
    ) -> ExternalResource:
        return ExternalResource(
            resource_id=f"mame-{name}",
            provider=self.provider,
            platform="mame",
            name=name,
            version=version,
            resource_type=ExternalResourceType.METADATA,
            url=f"{self.base_url}{page}",
            storage=ResourceStorage.SERM_METADATA,
            extraction=ExtractionMode.ARCHIVE,
            required=False,
            notes=f"Recurso publicado como {filename}; a pagina do provider resolve o download real.",
            metadata={"discovery_url": f"{self.base_url}{page}", "filename": filename},
        )


__all__ = ["ProgettoSnapsProvider"]
