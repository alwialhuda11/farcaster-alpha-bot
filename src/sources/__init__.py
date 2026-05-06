"""Pluggable Twitter sources. Each source returns a list of Tweet objects."""
from __future__ import annotations

from .apify_source import ApifySource
from .base import Tweet, TwitterSource
from .fixture_source import FixtureSource
from .xcancel_source import XCancelSource


def build_source(name: str, **kwargs: object) -> TwitterSource:
    """Factory: construct a source by name."""
    name = name.lower().strip()
    if name == "xcancel":
        return XCancelSource(**kwargs)  # type: ignore[arg-type]
    if name == "apify":
        return ApifySource(**kwargs)  # type: ignore[arg-type]
    if name == "fixture":
        return FixtureSource(**kwargs)  # type: ignore[arg-type]
    raise ValueError(f"Unknown TWITTER_SOURCE: {name!r}. Use one of: xcancel, apify, fixture.")


__all__ = ["Tweet", "TwitterSource", "build_source"]
