"""Provider isolado para recursos MAME publicados pelo Progetto-SNAPS.

A descoberta web fica concentrada aqui. O restante do SERM recebe apenas
``ExternalResource`` e nao conhece a navegacao manual do site.
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
    """Catalogo dos recursos externos selecionados para o SERM V2."""

    provider = "progetto_snaps"
    base_url = "https://www.progettosnaps.net"
    samples_url = f"{base_url}/samples/"
    support_url = f"{base_url}/support/"

    # These versions are intentionally explicit. The provider must not invent a
    # version from the current MAME version when the upstream resource has its
    # own release cadence (BestGames and Command are examples).
    _PACKAGES = (
        {
            "name": "catver",
            "version": "0.289",
            "filename": "pS_CatVer_289.zip",
            "download": "/download/?file=pS_CatVer_289.zip&tipo=catver",
            "members": {
                "catver.ini": "serm_metadata",
                "UI_files/catlist.ini": "mame_folders",
                "UI_files/genre.ini": "mame_folders",
                "UI_files/genre_ows.ini": "serm_metadata",
                "UI_files/mature.ini": "serm_metadata",
                "UI_files/not_mature.ini": "serm_metadata",
            },
            "notes": "CatVer e usado por frontends; CatList/Genre sao os arquivos de classificacao relevantes ao MAME.",
        },
        {
            "name": "bestgames",
            "version": "0.280",
            "filename": "pS_BestGames_280.zip",
            "download": "/download/?file=pS_BestGames_280.zip&tipo=bestgames",
            "members": {"folders/bestgames.ini": "mame_folders"},
            "notes": "Ranking pessoal do autor; metadado opcional do Arcade Studio, nao criterio oficial de MAME.",
        },
        {
            "name": "series",
            "version": "0.289",
            "filename": "pS_Series_289.zip",
            "download": "/download/?file=pS_Series_289.zip&tipo=series",
            "members": {"folders/series.ini": "mame_folders"},
            "notes": "Agrupamento de series e variantes de jogos; util para navegacao/filtro.",
        },
        {
            "name": "languages",
            "version": "0.289",
            "filename": "pS_Languages_289.zip",
            "download": "/download/?file=pS_Languages_289.zip&tipo=languages",
            "members": {"folders/languages.ini": "mame_folders"},
            "notes": "Classificacao por idioma; arquivo destinado a Folders.",
        },
        {
            "name": "gameinit",
            "version": "0.289",
            "filename": "pS_gameinit_289.zip",
            "download": "/download/?file=pS_gameinit_289.zip&tipo=gameinit",
            "members": {
                "dats/gameinit.dat": "mame_dats",
                "folders/gameinit.ini": "mame_folders",
            },
            "notes": "Informacoes de inicializacao; DAT e INI sao complementares e devem ser mantidos separados.",
        },
        {
            "name": "command",
            "version": "0.273",
            "filename": "pS_Command_273.zip",
            "download": "/download/?file=pS_Command_273.zip&tipo=command",
            "members": {
                "dats/command.dat": "mame_dats",
                "folders/command.ini": "mame_folders",
            },
            "notes": "Comandos de jogos; pacote antigo em relacao ao MAME atual, portanto versionado independentemente.",
        },
    )

    def resources(self) -> tuple[ExternalResource, ...]:
        """Retorna os pacotes selecionados e o FullPack de Samples atual."""
        resources = [self._support_package(**package) for package in self._PACKAGES]
        resources.append(
            ExternalResource(
                resource_id="mame-samples-fullpack",
                provider=self.provider,
                platform="mame",
                name="samples-fullpack",
                version="0.289",
                resource_type=ExternalResourceType.SAMPLE,
                url="https://www.progettosnaps.net/samples/packs/MAME_samples_289.zip",
                storage=ResourceStorage.MAME_SOURCE,
                extraction=ExtractionMode.ARCHIVE,
                required=False,
                notes="FullPack MAME Samples 0.289; o site informa 75 ZIPs e alerta que alguns recursos individuais contem arquivos falsos.",
                metadata={
                    "listing_url": self.samples_url,
                    "package_count": 75,
                    "validate_individual_members": True,
                    "destination": "samples",
                },
            )
        )
        return tuple(resources)

    def catalog(self) -> ExternalResourceCatalog:
        """Constroi um catalogo pronto para consulta."""
        return ExternalResourceCatalog(self.resources())

    def _support_package(
        self,
        name: str,
        version: str,
        filename: str,
        download: str,
        members: dict[str, str],
        notes: str,
    ) -> ExternalResource:
        return ExternalResource(
            resource_id=f"mame-{name}",
            provider=self.provider,
            platform="mame",
            name=name,
            version=version,
            resource_type=ExternalResourceType.METADATA,
            url=f"{self.base_url}{download}",
            storage=ResourceStorage.MAME_SOURCE,
            extraction=ExtractionMode.ARCHIVE,
            required=False,
            notes=notes,
            metadata={
                "discovery_url": f"{self.base_url}/{name}/",
                "filename": filename,
                "members": members,
                "support_root": self.support_url,
            },
        )


__all__ = ["ProgettoSnapsProvider"]
