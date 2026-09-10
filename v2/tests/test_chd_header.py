import struct

import pytest

from serm_v2.services.chd_header import ChdFormatError, ChdHeaderReader


def test_reads_v5_raw_sha1_without_hashing_the_compressed_file(tmp_path) -> None:
    path = tmp_path / "disc.chd"
    raw_sha1 = bytes.fromhex("11" * 20)
    combined_sha1 = bytes.fromhex("22" * 20)
    parent_sha1 = bytes.fromhex("33" * 20)
    header = bytearray(124)
    header[0:8] = b"MComprHD"
    struct.pack_into(">II", header, 8, 124, 5)
    struct.pack_into(">Q", header, 32, 11280384)
    struct.pack_into(">Q", header, 40, 124)
    struct.pack_into(">Q", header, 48, 4096)
    struct.pack_into(">II", header, 56, 4096, 1024)
    header[64:84] = raw_sha1
    header[84:104] = combined_sha1
    header[104:124] = parent_sha1
    path.write_bytes(header + b"compressed payload")

    result = ChdHeaderReader().read(path)

    assert result.version == 5
    assert result.logical_bytes == 11280384
    assert result.hunk_bytes == 4096
    assert result.raw_sha1 == "11" * 20
    assert result.sha1 == "22" * 20
    assert result.parent_sha1 == "33" * 20
    assert result.md5 is None


def test_rejects_invalid_chd_tag(tmp_path) -> None:
    path = tmp_path / "invalid.chd"
    path.write_bytes(b"not-a-chd")

    with pytest.raises(ChdFormatError):
        ChdHeaderReader().read(path)
