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

    # O site oficial identifica este como o pacote de suporte mais recente
    # (0.288), mesmo enquanto category/version ja possuem pacotes 0.289.
    SUPPORT_VERSION = "0.288"
    SUPPORT_ARCHIVE = (
        f"{base_url}/download/?file=%2Fsupport%2Fpacks%2F"
        "pS_SupportFiles_288.zip&tipo=support_pack"
    )

    _SUPPORT_MEMBERS = {
        "dats/command.dat": "mame_dats",
        "dats/gameinit.dat": "mame_dats",
        "folders/bestgames.ini": "mame_folders",
        "folders/catlist.ini": "mame_folders",
        "folders/genre.ini": "mame_folders",
        "folders/languages.ini": "mame_folders",
        "folders/series.ini": "mame_folders",
        "folders/gameinit.ini": "mame_folders",
    }

    def resources(self) -> tuple[ExternalResource, ...]:
        """Retorna suporte principal, dados complementares e samples."""
        return (
            ExternalResource(
                resource_id="mame-support-files",
                provider=self.provider,
                platform="mame",
                name="support-files",
                version=self.SUPPORT_VERSION,
                resource_type=ExternalResourceType.METADATA,
                url=self.SUPPORT_ARCHIVE,
                storage=ResourceStorage.MAME_SOURCE,
                extraction=ExtractionMode.ARCHIVE,
                required=False,
                notes=(
                    "Pacote oficial de suporte MAME. O SERM publica somente "
                    "command.dat, gameinit.dat e os INI principais na arvore MAME."
                ),
                metadata={
                    "members": self._SUPPORT_MEMBERS,
                    "support_root": self.support_url,
                    "destination": "MAME",
                },
            ),
            self._special_package(
                name="category",
                version="0.289",
                filename="pS_category_289.zip",
                package_type="category",
                destination="folders",
            ),
            self._special_package(
                name="version",
                version="0.289",
                filename="pS_version_289.zip",
                package_type="version",
                destination="folders",
            ),
            ExternalResource(
                resource_id="mame-messinfo",
                provider=self.provider,
                platform="mame",
                name="messinfo",
                version="0.289",
                resource_type=ExternalResourceType.METADATA,
                url=f"{self.base_url}/download/?file=pS_messinfo_289.zip&tipo=messinfo",
                storage=ResourceStorage.MAME_SOURCE,
                extraction=ExtractionMode.ARCHIVE,
                required=False,
                notes=(
                    "MESSINFO.dat oficial 0.289. Apesar do nome historico, "
                    "o arquivo acompanha sistemas nao-arcade dentro do MAME."
                ),
                metadata={
                    "support_root": self.support_url,
                    "destination": "dats",
                    "archive_members": ("messinfo.dat",),
                },
            ),
            ExternalResource(
                resource_id="mame-dat-index",
                provider=self.provider,
                platform="mame",
                name="mame-dat-index",
                version="0.289",
                resource_type=ExternalResourceType.METADATA,
                url=self.mame_dat_url,
                storage=ResourceStorage.CACHE_ONLY,
                extraction=ExtractionMode.NONE,
                required=False,
                notes=(
                    "Indice oficial dos DATs MAME. O SERM consulta este catalogo "
                    "antes de materializar o DAT como dado de auditoria."
                ),
                metadata={"listing_url": self.mame_dat_url},
            ),
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
                notes=(
                    "FullPack oficial de MAME Samples 0.289. Os ZIPs internos "
                    "devem ser publicados diretamente em MAME/samples/."
                ),
                metadata={
                    "listing_url": self.samples_url,
                    "destination": "samples",
                    "install_all_members_to": "mame_samples",
                },
            ),
        )

    def catalog(self) -> ExternalResourceCatalog:
        """Cria o catalogo indexavel dos recursos do provider."""
        return ExternalResourceCatalog(self.resources())

    def _special_package(
        self,
        *,
        name: str,
        version: str,
        filename: str,
        package_type: str,
        destination: str,
    ) -> ExternalResource:
        """Cria os pacotes category/version mantendo a URL oficial."""
        return ExternalResource(
            resource_id=f"mame-{name}",
            provider=self.provider,
            platform="mame",
            name=name,
            version=version,
            resource_type=ExternalResourceType.METADATA,
            url=(
                f"{self.base_url}/download/?file=%2Fsupport%2Fpacks%2F"
                f"{filename}&tipo={package_type}"
            ),
            storage=ResourceStorage.MAME_SOURCE,
            extraction=ExtractionMode.ARCHIVE,
            required=False,
            notes=f"Pacote oficial {name}.ini {version}.",
            metadata={
                "support_root": self.support_url,
                "destination": destination,
                "package_type": package_type,
            },
        )


__all__ = ["ProgettoSnapsProvider"]
