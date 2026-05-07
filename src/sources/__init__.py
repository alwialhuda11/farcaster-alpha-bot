"""Pluggable content sources. Each source returns a list of Tweet objects (the
type is named for historical reasons; today it represents any post-able item:
crypto news, tweets, or fixtures)."""
from __future__ import annotations

from .apify_source import ApifySource
from .base import Tweet, TwitterSource
from .fixture_source import FixtureSource
from .news_rss_source import NewsRSSSource
from .xcancel_source import XCancelSource


def build_source(name: str, **kwargs: object) -> TwitterSource:
    """Factory: construct a source by name."""
    name = name.lower().strip()
    if name in ("news_rss", "news", "rss"):
        return NewsRSSSource(**kwargs)  # type: ignore[arg-type]
    if name == "xcancel":
        return XCancelSource(**kwargs)  # type: ignore[arg-type]
    if name == "apify":
        return ApifySource(**kwargs)  # type: ignore[arg-type]
    if name == "fixture":
        return FixtureSource(**kwargs)  # type: ignore[arg-type]
    raise ValueError(
        f"Unknown TWITTER_SOURCE: {name!r}. "
        "Use one of: news_rss (recommended), xcancel, apify, fixture."
    )


__all__ = ["NewsRSSSource", "Tweet", "TwitterSource", "build_source"]
