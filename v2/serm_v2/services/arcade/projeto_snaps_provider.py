"""Catalogo oficial de suporte MAME publicado pelo progetto-SNAPS."""

from __future__ import annotations

from ...models.external_resource import (
    ExternalResource,
    ExternalResourceType,
    ExtractionMode,
    ResourceStorage,
)
from .resource_catalog import ExternalResourceCatalog


class ProgettoSnapsProvider:
    """Define os pacotes oficiais que o SERM pode instalar na arvore MAME."""

    provider = "progetto_snaps"
    base_url = "https://www.progettosnaps.net"
    support_url = f"{base_url}/support/"
    samples_url = f"{base_url}/samples/"
    mame_dat_url = f"{base_url}/dats/MAME/"

    nplayers_primary_url = "https://nplayers.arcadebelgium.be/files/nplayers0278.zip"
    nplayers_mirror_url = "https://www.planetemu.net/php/utilitaires/?action=download&id=181"

    SUPPORT_VERSION = "0.288"
    SUPPORT_ARCHIVE = (
        f"{base_url}/download/?file=%2Fsupport%2Fpacks%2F"
        "pS_SupportFiles_288.zip&tipo=support_pack"
    )

    _SUPPORT_MEMBERS = {
        "dats/command.dat": "mame_dats", "dats/gameinit.dat": "mame_dats",
        "folders/bestgames.ini": "mame_folders", "folders/catlist.ini": "mame_folders",
        "folders/freeplay.ini": "mame_folders", "folders/genre.ini": "mame_folders",
        "folders/languages.ini": "mame_folders", "folders/monochrome.ini": "mame_folders",
        "folders/resolution.ini": "mame_folders", "folders/screenless.ini": "mame_folders",
        "folders/series.ini": "mame_folders",
    }

    NPLAYERS_VERSION = "0.278"
    NPLAYERS_ARCHIVE = nplayers_primary_url

    _CATEGORY_MEMBERS = (
        "ArcadeWokingParents.ini", "Artwork_Necessary.ini", "Bootleg.ini", "Category.ini",
        "CHD.ini", "CHD_Working.ini", "Clones Arcade.ini", "Driver.ini", "FreePlay.ini",
        "MAME.ini", "MAME_BIOS.ini", "MAME_NOBIOS.ini", "Mechanicals Arcade.ini", "MESS.ini",
        "MonoChrome.ini", "Non Bootleg.ini", "Non Mechanicals Arcade.ini", "Not Working Arcade.ini",
        "Parents Arcade.ini", "Prototype.ini", "Resolution.ini", "Screenless.ini", "Use Software.ini",
        "Working Arcade.ini", "Working Arcade Clean.ini",
    )
    _VERSION_MEMBERS = ("Version.ini", "Version_NEW.ini", "Version_ON.ini")

    def resources(self) -> tuple[ExternalResource, ...]:
        return (
            ExternalResource(
                resource_id="mame-support-files", provider=self.provider, platform="mame", name="support-files",
                version=self.SUPPORT_VERSION, resource_type=ExternalResourceType.METADATA, url=self.SUPPORT_ARCHIVE,
                storage=ResourceStorage.MAME_SOURCE, extraction=ExtractionMode.ARCHIVE, required=False,
                notes="Pacote oficial de suporte MAME; a versao e descoberta automaticamente.",
                metadata={
                    "members": self._SUPPORT_MEMBERS, "support_root": self.support_url, "destination": "MAME",
                    "latest_discovery": {
                        "strategy": "listing", "listing_url": self.support_url,
                        "pattern": r"SupportFiles Pack\s*\((0\.\d+)\)",
                        "url_template": f"{self.base_url}/download/?file=%2Fsupport%2Fpacks%2FpS_SupportFiles_{{version_compact}}.zip&tipo=support_pack",
                    },
                },
            ),
            ExternalResource(
                resource_id="mame-nplayers", provider=self.provider, platform="mame", name="nplayers",
                version=self.NPLAYERS_VERSION, resource_type=ExternalResourceType.METADATA, url=self.NPLAYERS_ARCHIVE,
                storage=ResourceStorage.MAME_SOURCE, extraction=ExtractionMode.ARCHIVE, required=False,
                notes="NPlayers.ini; a fonte original e tentada primeiro e o Planet Emulation permanece como fallback.",
                metadata={
                    "members": {"nplayers.ini": "mame_folders"}, "source_page": self.support_url,
                    "original_source": "https://nplayers.arcadebelgium.be/", "fallback_urls": (self.nplayers_mirror_url,),
                    "destination": "folders",
                    "latest_discovery": {
                        "strategy": "probe", "start_version": self.NPLAYERS_VERSION, "max_ahead": 30,
                        "stop_after_misses": 3, "fallback_only_version": self.NPLAYERS_VERSION,
                        "url_template": "https://nplayers.arcadebelgium.be/files/nplayers{version_compact}.zip",
                    },
                },
            ),
            self._special_package(name="category", version="0.289", filename="pS_category_289.zip", package_type="category", destination="folders", expected_members=self._CATEGORY_MEMBERS),
            self._special_package(name="version", version="0.289", filename="pS_version_289.zip", package_type="version", destination="folders", expected_members=self._VERSION_MEMBERS),
            ExternalResource(
                resource_id="mame-messinfo", provider=self.provider, platform="mame", name="messinfo", version="0.289",
                resource_type=ExternalResourceType.METADATA, url=f"{self.base_url}/download/?file=pS_messinfo_289.zip&tipo=messinfo",
                storage=ResourceStorage.MAME_SOURCE, extraction=ExtractionMode.ARCHIVE, required=False,
                notes="MESSINFO.dat oficial; a versao e descoberta na pagina do projeto.",
                metadata={
                    "support_root": self.support_url, "destination": "dats", "archive_members": ("messinfo.dat",),
                    "latest_discovery": {
                        "strategy": "listing", "listing_url": f"{self.base_url}/messinfo/",
                        "pattern": r"\b(0\.\d{3})\s*:",
                        "url_template": f"{self.base_url}/download/?file=pS_messinfo_{{version_compact}}.zip&tipo=messinfo",
                    },
                },
            ),
            ExternalResource(
                resource_id="mame-dat-index", provider=self.provider, platform="mame", name="mame-dat-index", version="0.289",
                resource_type=ExternalResourceType.METADATA, url=self.mame_dat_url, storage=ResourceStorage.CACHE_ONLY,
                extraction=ExtractionMode.NONE, required=False,
                notes="Indice oficial dos DATs MAME; sua pagina e usada como fonte de versao.", metadata={"listing_url": self.mame_dat_url},
            ),
            ExternalResource(
                resource_id="mame-samples-fullpack", provider=self.provider, platform="mame", name="samples-fullpack", version="0.289",
                resource_type=ExternalResourceType.SAMPLE, url=f"{self.base_url}/samples/",
                storage=ResourceStorage.MAME_SOURCE, extraction=ExtractionMode.ARCHIVE, required=False,
                notes="FullPack oficial de MAME Samples; o link real e descoberto diretamente na pagina de Samples.",
                metadata={
                    "listing_url": self.samples_url, "source_page": self.samples_url, "destination": "samples", "install_all_members_to": "mame_samples",
                    "latest_discovery": {
                        "strategy": "link", "listing_url": self.samples_url,
                        "href_pattern": r"MAME_samples_(0\.\d{3})\.zip",
                    },
                },
            ),
        )

    def catalog(self) -> ExternalResourceCatalog:
        return ExternalResourceCatalog(self.resources())

    def _special_package(self, *, name: str, version: str, filename: str, package_type: str, destination: str, expected_members: tuple[str, ...]) -> ExternalResource:
        return ExternalResource(
            resource_id=f"mame-{name}", provider=self.provider, platform="mame", name=name, version=version,
            resource_type=ExternalResourceType.METADATA,
            url=f"{self.base_url}/download/?file=%2Fsupport%2Fpacks%2F{filename}&tipo={package_type}",
            storage=ResourceStorage.MAME_SOURCE, extraction=ExtractionMode.ARCHIVE, required=False,
            notes=f"Pacote oficial {name}.ini; a versao e descoberta automaticamente.",
            metadata={
                "support_root": self.support_url, "destination": destination, "package_type": package_type,
                "expected_members": expected_members,
                "latest_discovery": {
                    "strategy": "listing", "listing_url": self.support_url,
                    "pattern": rf"{name}\.ini\s*\((0\.\d+)\)",
                    "url_template": f"{self.base_url}/download/?file=%2Fsupport%2Fpacks%2FpS_{name}_{{version_compact}}.zip&tipo={package_type}",
                },
            },
        )


__all__ = ["ProgettoSnapsProvider"]
