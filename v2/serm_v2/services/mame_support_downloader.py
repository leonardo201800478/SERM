"""Download resiliente de arquivos de suporte MAME.

A rotina tenta primeiro a fonte primária configurada e depois a fonte
alternativa do GitHub. O conteúdo retornado pode ser persistido pelo
pipeline de ingestão existente, que é responsável por hash/proveniência.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .mame_support_sources import MameSupportSource


@dataclass(frozen=True, slots=True)
class DownloadedSupportFile:
    """Resultado de uma aquisição de arquivo de suporte."""

    source: MameSupportSource
    url: str
    content: bytes


class MameSupportDownloader:
    """Obtém arquivos de suporte usando fallback entre fontes."""

    def __init__(self, timeout: float = 30.0, user_agent: str = "SERM-V2") -> None:
        self.timeout = timeout
        self.user_agent = user_agent

    def download(self, source: MameSupportSource) -> DownloadedSupportFile:
        """Baixa uma fonte, tentando as URLs configuradas em sequência.

        Levanta `RuntimeError` somente quando todas as fontes falham, mantendo
        no erro as URLs tentadas para facilitar diagnóstico.
        """
        errors: list[str] = []
        for url in source.urls:
            request = Request(url, headers={"User-Agent": self.user_agent})
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    content = response.read()
                return DownloadedSupportFile(source=source, url=url, content=content)
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                errors.append(f"{url}: {exc}")
        raise RuntimeError(
            f"Não foi possível obter {source.name}. Fontes tentadas: " + " | ".join(errors)
        )


__all__ = ["DownloadedSupportFile", "MameSupportDownloader"]
