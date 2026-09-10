"""Descoberta generica da versao mais recente de recursos externos."""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import replace
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

from ...models.external_resource import ExternalResource


class _HrefParser(HTMLParser):
    """Extrai hrefs de uma pagina sem depender de bibliotecas externas."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        for name, value in attrs:
            if name.casefold() == "href" and value:
                self.hrefs.append(value)
                break


class LatestResourceResolver:
    """Resolve recursos declarados como atualizaveis antes do download."""

    def resolve(self, resource: ExternalResource) -> ExternalResource:
        spec = resource.metadata.get("latest_discovery")
        if not isinstance(spec, dict):
            return resource
        strategy = spec.get("strategy")
        try:
            if strategy == "listing":
                version, url = self._from_listing(resource, spec)
            elif strategy == "link":
                version, url = self._from_link_listing(resource, spec)
            elif strategy == "probe":
                version, url = self._from_probe(resource, spec)
            else:
                raise ValueError(f"estrategia de descoberta desconhecida: {strategy}")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
            return resource
        if not version or not url:
            return resource

        metadata = dict(resource.metadata)
        fallback_only_version = spec.get("fallback_only_version")
        if fallback_only_version is not None and version != fallback_only_version:
            metadata["fallback_urls"] = ()
        return replace(resource, version=version, url=url, metadata=metadata)

    def _from_listing(self, resource: ExternalResource, spec: dict[str, Any]) -> tuple[str | None, str | None]:
        listing_url = spec.get("listing_url")
        pattern = spec.get("pattern")
        url_template = spec.get("url_template")
        if not all(isinstance(item, str) and item for item in (listing_url, pattern, url_template)):
            raise ValueError(f"latest_discovery invalido para {resource.name}")
        body = self._fetch_text(listing_url, resource)
        versions = sorted(set(re.findall(pattern, body, flags=re.IGNORECASE)), key=self._version_key)
        if not versions:
            return resource.version, resource.url
        version = versions[-1]
        return version, self._format_url(url_template, version)

    def _from_link_listing(self, resource: ExternalResource, spec: dict[str, Any]) -> tuple[str | None, str | None]:
        listing_url = spec.get("listing_url")
        href_pattern = spec.get("href_pattern")
        if not isinstance(listing_url, str) or not listing_url:
            raise ValueError(f"listing_url ausente para {resource.name}")
        if not isinstance(href_pattern, str) or not href_pattern:
            raise ValueError(f"href_pattern ausente para {resource.name}")

        body = self._fetch_text(listing_url, resource)
        parser = _HrefParser()
        parser.feed(body)
        matches: list[tuple[str, str]] = []
        for href in parser.hrefs:
            match = re.search(href_pattern, href, flags=re.IGNORECASE)
            if match is None:
                continue
            if match.lastindex:
                version = match.group(1)
            else:
                version = resource.version
            matches.append((version, urljoin(listing_url, href)))

        if not matches:
            return resource.version, resource.url
        version, url = max(matches, key=lambda item: self._version_key(item[0]))
        return version, url

    def _from_probe(self, resource: ExternalResource, spec: dict[str, Any]) -> tuple[str | None, str | None]:
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
            candidate = ".".join(str(part) for part in self._increment_version(current, offset))
            url = self._format_url(url_template, candidate)
            if self._url_exists(url, resource):
                best_version = candidate
                misses = 0
            else:
                misses += 1
                if misses >= stop_after_misses:
                    break
        return best_version, self._format_url(url_template, best_version)

    @staticmethod
    def _format_url(template: str, version: str) -> str:
        return template.format(version=version, version_compact=version.replace(".", ""))

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
        request = urllib.request.Request(url, headers=LatestResourceResolver._headers(resource))
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _url_exists(url: str, resource: ExternalResource) -> bool:
        request = urllib.request.Request(
            url,
            headers={**LatestResourceResolver._headers(resource), "Range": "bytes=0-0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                response.read(1)
            return True
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            return False

    @staticmethod
    def _headers(resource: ExternalResource) -> dict[str, str]:
        headers = {
            "User-Agent": "SERM/2.x (+https://github.com/leonardo201800478/SERM)",
            "Accept": "text/html,application/zip,application/octet-stream,*/*",
        }
        source_page = resource.metadata.get("source_page")
        support_root = resource.metadata.get("support_root")
        original_source = resource.metadata.get("original_source")
        if isinstance(source_page, str) and source_page:
            headers["Referer"] = source_page
        elif isinstance(support_root, str) and support_root:
            headers["Referer"] = support_root
        elif isinstance(original_source, str) and original_source:
            headers["Referer"] = original_source
        return headers


__all__ = ["LatestResourceResolver"]
