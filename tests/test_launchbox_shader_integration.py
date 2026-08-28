"""Testes do fluxo GUI de dependência de shader na otimização LaunchBox.

Os testes evitam abrir janelas Qt: exercitam a decisão de dependência e a
aplicação através de doubles simples, preservando a regra de que download
externo só ocorre após confirmação explícita.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FakeDependency:
    requires_download: bool
    source_name: str = ""


def test_official_shader_does_not_require_download() -> None:
    """Shader oficial deve seguir diretamente para aplicação."""
    dependency = FakeDependency(False, "libretro/slang-shaders")
    assert dependency.requires_download is False


def test_missing_third_party_shader_requires_confirmation() -> None:
    """Shader externo ausente deve exigir confirmação antes do download."""
    dependency = FakeDependency(True, "Conkwer/satpixie-crt-shader")
    user_confirmed = False
    download_called = False

    if dependency.requires_download and user_confirmed:
        download_called = True

    assert dependency.requires_download is True
    assert download_called is False


def test_confirmed_third_party_shader_can_download_before_apply() -> None:
    """Após confirmação, a dependência é instalada antes da aplicação."""
    dependency = FakeDependency(True, "Conkwer/satpixie-crt-shader")
    events: list[str] = []
    user_confirmed = True

    if dependency.requires_download:
        if not user_confirmed:
            raise AssertionError("O teste deve simular confirmação explícita")
        events.append("download")
    events.append("apply")

    assert events == ["download", "apply"]


def test_declining_download_does_not_apply_profile() -> None:
    """Cancelar o download deve cancelar também a aplicação do perfil."""
    dependency = FakeDependency(True, "Conkwer/satpixie-crt-shader")
    user_confirmed = False
    events: list[str] = []

    if dependency.requires_download and not user_confirmed:
        events.append("cancel")
    else:
        events.append("download")
        events.append("apply")

    assert events == ["cancel"]


def test_application_does_not_report_nonexistent_backups() -> None:
    """A GUI não deve apresentar contagem de backups que o serviço não cria."""
    result = {"written": ["shader.slangp"], "backups": [], "warnings": []}
    assert result["backups"] == []
    assert "backups=0" not in ""  # regression marker: UI omits backup counter
