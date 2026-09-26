import hashlib
from pathlib import Path

from serm_v2.services.download_engine import (
    DownloadEngine,
    DownloadEngineConfig,
)


class _FakeResponse:
    def __init__(self, payload: bytes, status: int, headers: dict[str, str]) -> None:
        self._payload = payload
        self.status = status
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk, self._payload = self._payload, b""
            return chunk
        chunk, self._payload = self._payload[:size], self._payload[size:]
        return chunk


def test_parallel_download_uses_ranges_and_validates_hash(monkeypatch, tmp_path: Path) -> None:
    payload = bytes(range(256)) * 4096
    calls: list[str] = []

    def fake_urlopen(request, timeout):
        range_header = request.headers.get("Range", "")
        calls.append(range_header)
        if range_header == "bytes=0-0":
            return _FakeResponse(
                payload[:1],
                206,
                {"Content-Range": f"bytes 0-0/{len(payload)}"},
            )
        start, end = (int(value) for value in range_header.removeprefix("bytes=").split("-"))
        return _FakeResponse(
            payload[start : end + 1],
            206,
            {"Content-Range": f"bytes {start}-{end}/{len(payload)}"},
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    target = tmp_path / "pack.zip"
    digest = hashlib.sha256(payload).hexdigest()
    engine = DownloadEngine(
        DownloadEngineConfig(
            max_connections=3,
            segment_size=4096,
            chunk_size=1024,
            retries=2,
        )
    )

    result = engine.download(
        "https://example.invalid/pack.zip",
        target,
        expected_size=len(payload),
        expected_sha256=digest,
    )

    assert result == target
    assert target.read_bytes() == payload
    assert "bytes=0-0" in calls
    assert sum(1 for value in calls if value != "bytes=0-0") == 3


def test_download_resumes_completed_segments(monkeypatch, tmp_path: Path) -> None:
    payload = b"abcdefgh" * 1024
    work_dir = tmp_path / ".pack.zip.download"
    work_dir.mkdir()
    (work_dir / "segment-0000.part").write_bytes(payload[: len(payload) // 2])

    calls: list[str] = []

    def fake_urlopen(request, timeout):
        range_header = request.headers.get("Range", "")
        calls.append(range_header)
        if range_header == "bytes=0-0":
            return _FakeResponse(
                payload[:1],
                206,
                {"Content-Range": f"bytes 0-0/{len(payload)}"},
            )
        raw_range = range_header.removeprefix("bytes=")
        start_text, separator, end_text = raw_range.partition("-")
        start = int(start_text)
        end = int(end_text) if separator and end_text else len(payload) - 1
        return _FakeResponse(
            payload[start : end + 1],
            206,
            {"Content-Range": f"bytes {start}-{end}/{len(payload)}"},
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    target = tmp_path / "pack.zip"
    engine = DownloadEngine(
        DownloadEngineConfig(max_connections=1, segment_size=len(payload), chunk_size=128)
    )
    engine.download(
        "https://example.invalid/pack.zip",
        target,
        expected_size=len(payload),
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )

    assert target.read_bytes() == payload
    assert f"bytes={len(payload) // 2}-{len(payload) - 1}" in calls
