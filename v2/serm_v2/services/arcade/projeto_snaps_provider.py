"""Provider isolado para recursos MAME publicados pelo Progetto-SNAPS."""

from __future__ import annotations

from ...models.external_resource import (
    ExternalResource,
    ExternalResourceType,
    ExtractionMode,
    ResourceStorage,
)
from .resource_catalog import ExternalResourceCatalog


class ProgettoSnapsProvider:
    """Catalogo declarativo dos recursos externos selecionados para o SERM V2."""

    provider = "progetto_snaps"
    base_url = "https://www.progettosnaps.net"
    samples_url = f"{base_url}/samples/"
    support_url = f"{base_url}/support/"

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
            "notes": "Classificacao complementar; CatList e Genre podem alimentar filtros, sem substituir o ListXML.",
        },
        {
            "name": "bestgames",
            "version": "0.280",
            "filename": "pS_BestGames_280.zip",
            "download": "/download/?file=pS_BestGames_280.zip&tipo=bestgames",
            "members": {"folders/bestgames.ini": "mame_folders"},
            "notes": "Curadoria opcional; nao e criterio oficial do MAME.",
        },
        {
            "name": "series",
            "version": "0.289",
            "filename": "pS_Series_289.zip",
            "download": "/download/?file=pS_Series_289.zip&tipo=series",
            "members": {"folders/series.ini": "mame_folders"},
            "notes": "Agrupamento de series para navegacao e filtros.",
        },
        {
            "name": "languages",
            "version": "0.289",
            "filename": "pS_Languages_289.zip",
            "download": "/download/?file=pS_Languages_289.zip&tipo=languages",
            "members": {"folders/languages.ini": "mame_folders"},
            "notes": "Classificacao por idioma.",
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
            "notes": "Informacoes auxiliares de inicializacao.",
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
            "notes": "Informacoes auxiliares de comandos; versionado independentemente do MAME atual.",
        },
    )

    def resources(self) -> tuple[ExternalResource, ...]:
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
                notes="FullPack MAME Samples 0.289; deve ser validado contra as dependencias MAME antes da promocao para source confiavel.",
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
