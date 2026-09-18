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
    samples_url = f"{base_url}/samples/packs/MAME_samples_289.zip"
    NPLAYERS_ARCHIVE = "https://nplayers.arcadebelgium.be/files/nplayers0278.zip"
    support_url = f"{base_url}/support/"
    _CATEGORY_MEMBERS = tuple(f"folders/category_{index:02d}.ini" for index in range(25))
    _VERSION_MEMBERS = ("folders/version.ini", "folders/version_older.ini", "folders/version_new.ini")
    _SUPPORT_MEMBERS = {
        "dats/command.dat": "mame_dats",
        "dats/gameinit.dat": "mame_dats",
        "folders/bestgames.ini": "mame_folders",
        "folders/catlist.ini": "mame_folders",
        "folders/freeplay.ini": "mame_folders",
        "folders/genre.ini": "mame_folders",
        "folders/languages.ini": "mame_folders",
        "folders/monochrome.ini": "mame_folders",
        "folders/resolution.ini": "mame_folders",
        "folders/screenless.ini": "mame_folders",
        "folders/series.ini": "mame_folders",
    }

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
        resources = list(self._legacy_resources())
        resources.extend(self._support_package(**package) for package in self._PACKAGES)
        return tuple(resources)

    def catalog(self) -> ExternalResourceCatalog:
        """Retorna o conjunto canônico de recursos instaláveis pelo MAME."""
        return ExternalResourceCatalog(self._legacy_resources())

    def _legacy_resources(self) -> tuple[ExternalResource, ...]:
        """Retorna os pacotes históricos consumidos pela página de suporte."""
        return (
            self._support_package(
                name="support-files",
                version="0.289",
                filename="pS_Support_289.zip",
                download="/download/?file=pS_Support_289.zip&tipo=support",
                members=self._SUPPORT_MEMBERS,
                notes="Arquivos de suporte MAME mantidos pelo projeto-SNAPS.",
            ),
            ExternalResource(
                resource_id="mame-nplayers",
                provider=self.provider,
                platform="mame",
                name="nplayers",
                version="0.278",
                resource_type=ExternalResourceType.METADATA,
                url=self.NPLAYERS_ARCHIVE,
                storage=ResourceStorage.MAME_SOURCE,
                extraction=ExtractionMode.ARCHIVE,
                notes="Pacote NPlayers oficial com mirror PlanetEMU.",
                metadata={
                    "members": {"nplayers.ini": "mame_folders"},
                    "original_source": "https://nplayers.arcadebelgium.be/",
                    "fallback_urls": ("https://www.planetemu.net/php/utilitaires/?action=download&id=181",),
                    "latest_discovery": {"url_template": "https://nplayers.arcadebelgium.be/files/nplayers{version}.zip"},
                },
            ),
            self._manifest_resource("category", self._CATEGORY_MEMBERS),
            self._manifest_resource("version", self._VERSION_MEMBERS),
            ExternalResource(
                resource_id="mame-messinfo",
                provider=self.provider,
                platform="mame",
                name="messinfo",
                version="0.289",
                resource_type=ExternalResourceType.METADATA,
                url=f"{self.base_url}/download/?file=pS_messinfo_289.zip&tipo=messinfo",
                storage=ResourceStorage.MAME_SOURCE,
                metadata={"archive_members": ("messinfo.dat",)},
            ),
            ExternalResource(
                resource_id="mame-dat-index",
                provider=self.provider,
                platform="mame",
                name="dat-index",
                version="0.289",
                resource_type=ExternalResourceType.METADATA,
                url=f"{self.base_url}/dats/MAME/",
                storage=ResourceStorage.MAME_SOURCE,
                extraction=ExtractionMode.NONE,
            ),
            self._samples_resource(),
        )

    def _manifest_resource(self, name: str, members: tuple[str, ...]) -> ExternalResource:
        return ExternalResource(
            resource_id=f"mame-{name}",
            provider=self.provider,
            platform="mame",
            name=name,
            version="0.289",
            resource_type=ExternalResourceType.METADATA,
            url=f"{self.base_url}/download/?file=pS_{name.title()}_289.zip&tipo={name}",
            storage=ResourceStorage.MAME_SOURCE,
            metadata={"expected_members": members},
        )

    def _samples_resource(self) -> ExternalResource:
        return ExternalResource(
            resource_id="mame-samples-fullpack",
            provider=self.provider,
            platform="mame",
            name="samples-fullpack",
            version="0.289",
            resource_type=ExternalResourceType.SAMPLE,
            url=self.samples_url,
            storage=ResourceStorage.MAME_SOURCE,
            metadata={
                "source_page": self.samples_url,
                "latest_discovery": {
                    "strategy": "link",
                    "listing_url": self.samples_url,
                    "href_pattern": r"MAME_samples_(0\.\d{3})\.zip",
                },
            },
        )

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
