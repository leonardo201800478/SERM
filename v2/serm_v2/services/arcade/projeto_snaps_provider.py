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

    # NPlayers e uma referencia externa na pagina do progetto-SNAPS. O
    # arquivo oficial e publicado diretamente pelo Arcade Belgium; o Planet
    # Emulation permanece apenas como fallback porque pode bloquear clientes
    # automatizados com HTTP 403.
    nplayers_primary_url = "http://nplayers.arcadebelgium.be/files/nplayers0278.zip"
    nplayers_mirror_url = "https://www.planetemu.net/php/utilitaires/?action=download&id=181"

    # O site oficial identifica este como o pacote de suporte mais recente
    # (0.288), mesmo enquanto category/version ja possuem pacotes 0.289.
    SUPPORT_VERSION = "0.288"
    SUPPORT_ARCHIVE = (
        f"{base_url}/download/?file=%2Fsupport%2Fpacks%2F"
        "pS_SupportFiles_288.zip&tipo=support_pack"
    )

    # O SupportFiles Pack nao e um espelho de todos os links exibidos na
    # pagina de suporte. History.dat, mameinfo.dat, hiscore.dat,
    # unoffsysinfo.dat e nplayers.ini sao referencias externas mantidas
    # fora do ZIP pS_SupportFiles_288.zip. O SERM deve instalar somente os
    # membros que realmente fazem parte do pacote oficial que esta baixando.
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

    NPLAYERS_VERSION = "0.278"
    NPLAYERS_ARCHIVE = nplayers_primary_url

    # Pacote category 0.289 publicado pelo site oficial.
    _CATEGORY_MEMBERS = (
        "ArcadeWokingParents.ini",
        "Artwork_Necessary.ini",
        "Bootleg.ini",
        "Category.ini",
        "CHD.ini",
        "CHD_Working.ini",
        "Clones Arcade.ini",
        "Driver.ini",
        "FreePlay.ini",
        "MAME.ini",
        "MAME_BIOS.ini",
        "MAME_NOBIOS.ini",
        "Mechanicals Arcade.ini",
        "MESS.ini",
        "MonoChrome.ini",
        "Non Bootleg.ini",
        "Non Mechanicals Arcade.ini",
        "Not Working Arcade.ini",
        "Parents Arcade.ini",
        "Prototype.ini",
        "Resolution.ini",
        "Screenless.ini",
        "Use Software.ini",
        "Working Arcade.ini",
        "Working Arcade Clean.ini",
    )

    _VERSION_MEMBERS = (
        "Version.ini",
        "Version_NEW.ini",
        "Version_ON.ini",
    )

    def resources(self) -> tuple[ExternalResource, ...]:
        """Retorna suporte principal, classificacoes e samples."""
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
                    "os membros realmente presentes no SupportFiles Pack; "
                    "history.dat, mameinfo.dat, hiscore.dat, unoffsysinfo.dat "
                    "e nplayers.ini sao referencias externas na pagina oficial "
                    "e nao fazem parte deste ZIP."
                ),
                metadata={
                    "members": self._SUPPORT_MEMBERS,
                    "support_root": self.support_url,
                    "destination": "MAME",
                },
            ),
            ExternalResource(
                resource_id="mame-nplayers",
                provider=self.provider,
                platform="mame",
                name="nplayers",
                version=self.NPLAYERS_VERSION,
                resource_type=ExternalResourceType.METADATA,
                url=self.NPLAYERS_ARCHIVE,
                storage=ResourceStorage.MAME_SOURCE,
                extraction=ExtractionMode.ARCHIVE,
                required=False,
                notes=(
                    "NPlayers.ini 0.278, publicado originalmente pelo projeto "
                    "NPlayers/Arcade Belgium. O SERM tenta primeiro a fonte "
                    "original e usa o Planet Emulation somente como fallback. "
                    "O arquivo permite classificar jogos por numero de jogadores "
                    "e modo simultaneo/alternado e e instalado em MAME/folders/."
                ),
                metadata={
                    "members": {"nplayers.ini": "mame_folders"},
                    "source_page": self.support_url,
                    "original_source": "https://nplayers.arcadebelgium.be/",
                    "fallback_urls": (self.nplayers_mirror_url,),
                    "destination": "folders",
                },
            ),
            self._special_package(
                name="category",
                version="0.289",
                filename="pS_category_289.zip",
                package_type="category",
                destination="folders",
                expected_members=self._CATEGORY_MEMBERS,
            ),
            self._special_package(
                name="version",
                version="0.289",
                filename="pS_version_289.zip",
                package_type="version",
                destination="folders",
                expected_members=self._VERSION_MEMBERS,
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
        expected_members: tuple[str, ...],
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
                "expected_members": expected_members,
            },
        )


__all__ = ["ProgettoSnapsProvider"]
