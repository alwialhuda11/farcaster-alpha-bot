"""Unit tests for the NewsRSSSource (offline; uses fixture XML)."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from src.sources.news_rss_source import NewsRSSSource, _entry_id, _strip_html


def test_strip_html_basic() -> None:
    assert _strip_html("<p>hello <b>world</b></p>") == "hello world"
    assert _strip_html("<p>foo<br/>bar</p>") == "foo bar"
    assert _strip_html("") == ""
    assert _strip_html("plain") == "plain"


def test_entry_id_stable_across_runs() -> None:
    e = {"id": "guid-123", "link": "https://example.com/x"}
    assert _entry_id(e, "src") == _entry_id(e, "src")
    # different source name -> different id
    assert _entry_id(e, "src") != _entry_id(e, "other")


def _rss_bytes(items: list[tuple[str, str, str, str]]) -> bytes:
    """Build a minimal RSS doc with given (title, link, summary, pub_date) items."""
    inner = "".join(
        f"<item><title>{title}</title><link>{link}</link>"
        f"<description>{summary}</description><pubDate>{pub}</pubDate></item>"
        for title, link, summary, pub in items
    )
    return (
        '<?xml version="1.0"?><rss version="2.0"><channel>'
        f"<title>Test</title>{inner}</channel></rss>"
    ).encode()


def test_news_rss_parse_and_lookback() -> None:
    now = time.time()
    fresh_pub = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(now - 3600))
    stale_pub = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(now - 86400 * 5))
    body = _rss_bytes(
        [
            (
                "BTC tops 100k",
                "https://example.com/a",
                "Bitcoin briefly touched $100k.",
                fresh_pub,
            ),
            (
                "Old recap",
                "https://example.com/b",
                "Old news from days ago.",
                stale_pub,
            ),
        ]
    )

    fake_resp = MagicMock()
    fake_resp.content = body
    fake_resp.raise_for_status = MagicMock()

    src = NewsRSSSource(feeds=[("test", "https://example.com/rss")])
    with patch("src.sources.news_rss_source.requests.get", return_value=fake_resp) as mock_get:
        items = src.fetch(accounts=[], lookback_hours=12)
        mock_get.assert_called_once()

    # Only the fresh item should be returned.
    assert len(items) == 1
    item = items[0]
    assert item.author == "test"
    assert "BTC tops 100k" in item.text
    assert "Bitcoin briefly touched $100k." in item.text
    assert item.url == "https://example.com/a"
    assert item.created_ts > 0


def test_entry_ts_returns_utc_epoch() -> None:
    """`_entry_ts` must treat the feedparser struct as UTC (regression test for
    the bug where time.mktime() interpreted it as local time)."""
    from src.sources.news_rss_source import _entry_ts

    # 2025-01-15T12:00:00Z -> 1736942400
    ts_struct = time.struct_time((2025, 1, 15, 12, 0, 0, 2, 15, 0))
    ts = _entry_ts({"published_parsed": ts_struct})
    assert ts == 1736942400.0


def test_news_rss_dedup_across_feeds() -> None:
    """Same URL appearing in two feeds is returned once."""
    now = time.time()
    fresh_pub = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(now - 3600))
    body_a = _rss_bytes([("Shared headline", "https://shared.example/x", "summary", fresh_pub)])
    body_b = _rss_bytes(
        [
            ("Shared headline", "https://shared.example/x", "summary", fresh_pub),
            ("Unique to b", "https://b.example/y", "summary b", fresh_pub),
        ]
    )

    def fake_get(url: str, **_kwargs: object) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.content = body_a if "a-feed" in url else body_b
        return resp

    src = NewsRSSSource(
        feeds=[
            ("a", "https://example.com/a-feed"),
            ("b", "https://example.com/b-feed"),
        ]
    )
    with patch("src.sources.news_rss_source.requests.get", side_effect=fake_get):
        items = src.fetch(accounts=[], lookback_hours=12)

    urls = {it.url for it in items}
    assert urls == {"https://shared.example/x", "https://b.example/y"}
    assert len(items) == 2  # the shared URL is deduped


def test_news_rss_handles_feed_failure() -> None:
    """One feed failing must not break the whole fetch."""
    now = time.time()
    fresh_pub = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(now - 3600))
    body_ok = _rss_bytes([("ok title", "https://ok.example/x", "summary", fresh_pub)])

    def fake_get(url: str, **_kwargs: object) -> MagicMock:
        if "broken" in url:
            raise RuntimeError("network down")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.content = body_ok
        return resp

    src = NewsRSSSource(
        feeds=[
            ("broken", "https://example.com/broken-feed"),
            ("ok", "https://example.com/ok-feed"),
        ]
    )
    with patch("src.sources.news_rss_source.requests.get", side_effect=fake_get):
        items = src.fetch(accounts=[], lookback_hours=12)

    assert len(items) == 1
    assert items[0].author == "ok"
