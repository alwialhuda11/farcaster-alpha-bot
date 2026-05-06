"""Crypto news RSS source.

Pulls recent articles from a list of crypto news RSS feeds (CoinDesk, Decrypt,
The Block, Cointelegraph, The Defiant, etc.) and normalizes them into Tweet
objects so the rest of the pipeline (LLM rewriter, posting) works unchanged.

This source is the recommended default in 2025+ since direct Twitter scraping
without a paid API/Apify plan is unreliable.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass

import feedparser
import requests

from .base import Tweet, TwitterSource

log = logging.getLogger(__name__)


# Default crypto news RSS feeds (working as of 2025-05).
DEFAULT_FEEDS: list[tuple[str, str]] = [
    ("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("decrypt", "https://decrypt.co/feed"),
    ("theblock", "https://www.theblock.co/rss.xml"),
    ("cointelegraph", "https://cointelegraph.com/rss"),
    ("thedefiant", "https://thedefiant.io/api/feed"),
    ("cryptoslate", "https://cryptoslate.com/feed/"),
]

USER_AGENT = "Mozilla/5.0 (compatible; FarcasterAlphaBot/1.0; +https://github.com/)"

_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _strip_html(s: str) -> str:
    """Strip HTML tags + collapse whitespace."""
    if not s:
        return ""
    s = _HTML_TAG.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


def _entry_id(entry: dict, source: str) -> str:
    """Stable ID per article: prefer guid/id, fallback to link, fallback to title hash."""
    cand = entry.get("id") or entry.get("guid") or entry.get("link") or entry.get("title", "")
    raw = f"{source}:{cand}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _entry_ts(entry: dict) -> float:
    """Best-effort published-time as unix seconds; 0 if unknown."""
    for key in ("published_parsed", "updated_parsed"):
        v = entry.get(key)
        if v:
            try:
                return time.mktime(v)
            except (TypeError, ValueError):
                continue
    return 0.0


@dataclass
class NewsRSSSource(TwitterSource):
    """Read recent items from a list of crypto news RSS feeds."""

    name: str = "news_rss"
    feeds: list[tuple[str, str]] | None = None
    timeout: int = 15
    user_agent: str = USER_AGENT
    per_feed_limit: int = 25

    def __post_init__(self) -> None:
        if self.feeds is None:
            self.feeds = list(DEFAULT_FEEDS)

    def fetch(self, accounts: list[str], lookback_hours: int) -> list[Tweet]:
        """`accounts` is ignored; news source uses configured feed URLs."""
        cutoff = time.time() - max(lookback_hours, 1) * 3600
        out: list[Tweet] = []
        feeds = self.feeds or DEFAULT_FEEDS
        for source_name, url in feeds:
            try:
                items = self._fetch_one(source_name, url, cutoff)
                log.info("news_rss: %s -> %d fresh items", source_name, len(items))
                out.extend(items)
            except Exception as e:
                log.warning("news_rss: %s failed: %s", source_name, e)
        log.info("news_rss: %d total items across %d feeds", len(out), len(feeds))
        return out

    def _fetch_one(self, source_name: str, url: str, cutoff_ts: float) -> list[Tweet]:
        resp = requests.get(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/rss+xml,text/xml,*/*"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        items: list[Tweet] = []
        for entry in parsed.entries[: self.per_feed_limit]:
            ts = _entry_ts(entry)
            if ts and ts < cutoff_ts:
                continue
            title = _strip_html(entry.get("title", "") or "")
            summary = _strip_html(entry.get("summary", "") or entry.get("description", "") or "")
            link = entry.get("link", "") or ""
            if not title and not summary:
                continue
            # Combine title + summary for the LLM, but cap to avoid bloating prompts.
            body = title
            if summary and summary.lower() != title.lower():
                body = f"{title}. {summary}"
            if len(body) > 1500:
                body = body[:1500].rstrip() + "..."
            items.append(
                Tweet(
                    id=_entry_id(entry, source_name),
                    author=source_name,
                    text=body,
                    url=link,
                    created_ts=ts,
                )
            )
        return items
