"""Descoberta generica da versao mais recente de recursos externos."""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import replace
from typing import Any

from ...models.external_resource import ExternalResource


class LatestResourceResolver:
    """Resolve recursos declarados como atualizaveis antes do download.

    Providers descrevem como descobrir a versao em ``metadata[latest_discovery]``.
    O mecanismo suporta pagina de catalogo e sondagem de URLs versionadas, sem
    assumir que a versao do recurso seja igual a versao do emulador.
    """

    def resolve(self, resource: ExternalResource) -> ExternalResource:
        spec = resource.metadata.get("latest_discovery")
        if not isinstance(spec, dict):
            return resource

        strategy = spec.get("strategy")
        if strategy == "listing":
            version, url = self._from_listing(resource, spec)
        elif strategy == "probe":
            version, url = self._from_probe(resource, spec)
        else:
            raise ValueError(f"estrategia de descoberta desconhecida: {strategy}")

        if not version or not url:
            return resource
        return replace(resource, version=version, url=url)

    def _from_listing(
        self,
        resource: ExternalResource,
        spec: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        listing_url = spec.get("listing_url")
        pattern = spec.get("pattern")
        url_template = spec.get("url_template")
        if not all(isinstance(item, str) and item for item in (listing_url, pattern, url_template)):
            raise ValueError(f"latest_discovery invalido para {resource.name}")

        body = self._fetch_text(listing_url, resource)
        versions = re.findall(pattern, body, flags=re.IGNORECASE)
        versions = sorted(set(versions), key=self._version_key)
        if not versions:
            return resource.version, resource.url
        version = versions[-1]
        return version, url_template.format(version=version)

    def _from_probe(
        self,
        resource: ExternalResource,
        spec: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        url_template = spec.get("url_template")
        start_version = spec.get("start_version", resource.version)
        max_ahead = spec.get("max_ahead", 20)
        stop_after_misses = spec.get("stop_after_misses", 2)
        if not isinstance(url_template, str) or not url_template:
            raise ValueError(f"url_template ausente para {resource.name}")
        if not isinstance(start_version, str):
            raise ValueError(f"start_version invalido para {resource.name}")
        if not isinstance(max_ahead, int) or max_ahead < 1:
            raise ValueError(f"max_ahead invalido para {resource.name}")
        if not isinstance(stop_after_misses, int) or stop_after_misses < 1:
            raise ValueError(f"stop_after_misses invalido para {resource.name}")

        current = self._version_key(start_version)
        best_version = start_version
        misses = 0
        for offset in range(1, max_ahead + 1):
            candidate_key = self._increment_version(current, offset)
            candidate = ".".join(str(part) for part in candidate_key)
            url = url_template.format(version=candidate)
            if self._url_exists(url, resource):
                best_version = candidate
                misses = 0
            else:
                misses += 1
                if misses >= stop_after_misses:
                    break

        return best_version, url_template.format(version=best_version)

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        numbers = re.findall(r"\d+", version)
        return tuple(int(item) for item in numbers) or (0,)

    @staticmethod
    def _increment_version(base: tuple[int, ...], offset: int) -> tuple[int, ...]:
        if len(base) != 2:
            raise ValueError(f"versao nao suportada para sondagem: {base}")
        return (base[0], base[1] + offset)

    @staticmethod
    def _fetch_text(url: str, resource: ExternalResource) -> str:
        request = urllib.request.Request(
            url,
            headers=LatestResourceResolver._headers(resource, url),
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _url_exists(url: str, resource: ExternalResource) -> bool:
        request = urllib.request.Request(
            url,
            headers=LatestResourceResolver._headers(resource, url),
            method="HEAD",
        )
        try:
            with urllib.request.urlopen(request, timeout=15):
                return True
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            return False

    @staticmethod
    def _headers(resource: ExternalResource, url: str) -> dict[str, str]:
        headers = {
            "User-Agent": "SERM/2.x (+https://github.com/leonardo201800478/SERM)",
            "Accept": "text/html,application/zip,*/*",
        }
        referer = resource.metadata.get("support_root") or resource.metadata.get("original_source")
        if isinstance(referer, str) and referer:
            headers["Referer"] = referer
        return headers


__all__ = ["LatestResourceResolver"]
