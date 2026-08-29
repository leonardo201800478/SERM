from serm_v2.sources.no_intro.scene import NoIntroScene


def test_scene_resolves_published_link_for_system() -> None:
    html = '''
    <html><body>
      <a href="/files/Nintendo_-_Nintendo_Entertainment_System_20260829.zip">Nintendo - Nintendo Entertainment System</a>
      <a href="/files/other.zip">Other</a>
    </body></html>
    '''

    target = NoIntroScene().target_from_html(
        "Nintendo - Nintendo Entertainment System",
        html,
        "https://datomatic.no-intro.org/index.php?op=scene&page=download&s=25",
    )

    assert target.url.endswith("Nintendo_-_Nintendo_Entertainment_System_20260829.zip")
    assert target.revision is None


def test_scene_fetch_uses_numeric_system_id() -> None:
    captured: list[str] = []

    def fetch_html(url: str):
        captured.append(url)
        return (
            b'<a href="/files/NES.zip">Nintendo - Nintendo Entertainment System</a>',
            url,
            200,
        )

    target = NoIntroScene().fetch_target(
        "Nintendo - Nintendo Entertainment System",
        "25",
        fetch_html,
    )

    assert "&s=25" in captured[0]
    assert target.url.endswith("/files/NES.zip")
