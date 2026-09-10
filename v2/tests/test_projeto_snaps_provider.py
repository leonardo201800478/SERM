from __future__ import annotations

from serm_v2.services.arcade.projeto_snaps_provider import ProgettoSnapsProvider


def test_support_manifest_matches_pack_members() -> None:
    provider = ProgettoSnapsProvider()
    resource = next(item for item in provider.resources() if item.name == "support-files")
    members = resource.metadata["members"]

    assert isinstance(members, dict)
    assert len(members) == 12
    assert {
        "dats/command.dat",
        "dats/gameinit.dat",
        "folders/bestgames.ini",
        "folders/catlist.ini",
        "folders/freeplay.ini",
        "folders/genre.ini",
        "folders/languages.ini",
        "folders/monochrome.ini",
        "folders/nplayers.ini",
        "folders/resolution.ini",
        "folders/screenless.ini",
        "folders/series.ini",
    } == set(members)


def test_support_manifest_does_not_claim_external_files() -> None:
    provider = ProgettoSnapsProvider()
    resource = next(item for item in provider.resources() if item.name == "support-files")
    members = resource.metadata["members"]

    assert "dats/history.dat" not in members
    assert "dats/mameinfo.dat" not in members
    assert "dats/hiscore.dat" not in members
    assert "dats/unoffsysinfo.dat" not in members
    assert "folders/gameinit.ini" not in members


def test_category_and_version_manifests_are_complete() -> None:
    provider = ProgettoSnapsProvider()
    resources = {item.name: item for item in provider.resources()}

    category = resources["category"]
    version = resources["version"]

    assert category.version == "0.289"
    assert tuple(category.metadata["expected_members"]) == provider._CATEGORY_MEMBERS
    assert len(category.metadata["expected_members"]) == 25

    assert version.version == "0.289"
    assert tuple(version.metadata["expected_members"]) == provider._VERSION_MEMBERS
    assert len(version.metadata["expected_members"]) == 3


def test_messinfo_is_pinned_to_dedicated_0289_package() -> None:
    provider = ProgettoSnapsProvider()
    resource = next(item for item in provider.resources() if item.name == "messinfo")

    assert resource.version == "0.289"
    assert resource.metadata["archive_members"] == ("messinfo.dat",)
    assert resource.url.endswith("pS_messinfo_289.zip&tipo=messinfo")


def test_catalog_contains_all_projeto_snaps_resources() -> None:
    provider = ProgettoSnapsProvider()
    resources = provider.catalog().all()

    assert {item.resource_id for item in resources} == {
        "mame-support-files",
        "mame-category",
        "mame-version",
        "mame-messinfo",
        "mame-dat-index",
        "mame-samples-fullpack",
    }
