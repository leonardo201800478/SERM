"""Errors raised by the No-Intro source adapter."""


class NoIntroParseError(ValueError):
    """Raised when a No-Intro DAT cannot be parsed as expected."""


class NoIntroDownloadError(RuntimeError):
    """Raised when a No-Intro DAT cannot be downloaded."""
