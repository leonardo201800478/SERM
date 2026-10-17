"""TLS trust configuration shared by outbound HTTPS clients."""

from __future__ import annotations

import ssl

import certifi

DEFAULT_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


__all__ = ["DEFAULT_SSL_CONTEXT"]
