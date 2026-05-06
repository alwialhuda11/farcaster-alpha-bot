"""Twitter source via xcancel.com Nitter RSS feeds.

xcancel.com requires a one-time RSS-reader whitelist. See README -> "Twitter source: xcancel".
The first request from a new UA returns a feed whose <description> contains a token like
`bebbd13b...` — email that token to rss [AT] xcancel [DOT] com to get whitelisted.

Once whitelisted, subsequent feeds return real tweets.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup

from .base import Tweet, TwitterSource

log = logging.getLogger(__name__)

# Use an RSS-reader-style UA so xcancel returns the whitelist token / RSS body
# instead of the openresty 403 / "only works in an RSS client" 400.
USER_AGENT = "Mozilla/5.0 (compatible; FeedFetcher/1.0; +https://github.com/farcaster-alpha-bot)"
TIMEOUT = 20

# Mirrors of xcancel + a couple of public Nitter instances as fallbacks.
# We try them in order until one returns a parseable feed with at least one item.
INSTANCES = [
    "https://xcancel.com",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.tiekoetter.com",
]


class XCancelSource(TwitterSource):
    name = "xcancel"

    def __init__(self, instances: list[str] | None = None) -> None:
        self.instances = instances or INSTANCES

    def fetch(self, accounts: list[str], lookback_hours: int) -> list[Tweet]:
        cutoff_ts = time.time() - lookback_hours * 3600
        out: list[Tweet] = []
        for username in accounts:
            tweets = self._fetch_one(username, cutoff_ts)
            log.info("xcancel: %s -> %d tweets", username, len(tweets))
            out.extend(tweets)
        return out

    def _fetch_one(self, username: str, cutoff_ts: float) -> list[Tweet]:
        for instance in self.instances:
            url = f"{instance}/{username}/rss"
            try:
                resp = requests.get(
                    url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                    timeout=TIMEOUT,
                    allow_redirects=True,
                )
            except requests.RequestException as e:
                log.warning("xcancel: %s failed for @%s: %s", instance, username, e)
                continue

            if resp.status_code != 200 or not resp.content:
                log.warning(
                    "xcancel: %s returned HTTP %s for @%s", instance, resp.status_code, username
                )
                continue

            parsed = feedparser.parse(resp.content)
            title = (parsed.feed.get("title") or "").lower()
            if "rss reader not yet whitelisted" in title:
                desc = parsed.feed.get("description") or ""
                token_match = re.search(r"\b[a-f0-9]{32,}\b", desc)
                token = token_match.group(0) if token_match else "<see feed description>"
                log.error(
                    "xcancel: instance %s requires RSS whitelist for this server. "
                    "Email rss@xcancel.com with token: %s",
                    instance,
                    token,
                )
                # No point trying other accounts on this instance, but other instances may work.
                continue

            tweets = self._parse_feed(parsed, username, cutoff_ts)
            if tweets:
                return tweets
            log.info("xcancel: %s returned 0 items for @%s", instance, username)
        return []

    @staticmethod
    def _parse_feed(parsed: feedparser.FeedParserDict, username: str, cutoff_ts: float) -> list[Tweet]:
        tweets: list[Tweet] = []
        for entry in parsed.entries:
            link: str = entry.get("link", "")
            if not link:
                continue
            # Skip retweets when title starts with "RT by @username:"
            title: str = entry.get("title", "") or ""
            if title.startswith("RT by @"):
                continue
            tweet_id = link.rstrip("/").rsplit("/", 1)[-1].split("#")[0]
            if not tweet_id.isdigit():
                # Fallback: hash the link
                tweet_id = link

            text = _strip_html(entry.get("description", "") or title)
            if not text.strip():
                continue

            created_ts = _parse_pubdate(entry.get("published") or entry.get("updated"))
            if created_ts and created_ts < cutoff_ts:
                continue

            # Normalize the link to twitter.com so it works for any reader.
            twitter_url = f"https://twitter.com/{username}/status/{tweet_id}" if tweet_id.isdigit() else link
            tweets.append(
                Tweet(
                    id=tweet_id,
                    author=username,
                    text=text,
                    url=twitter_url,
                    created_ts=created_ts or 0.0,
                )
            )
        return tweets


_HTML_WS_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ")
    return _HTML_WS_RE.sub(" ", text).strip()


def _parse_pubdate(raw: str | None) -> float:
    if not raw:
        return 0.0
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.timestamp()
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
