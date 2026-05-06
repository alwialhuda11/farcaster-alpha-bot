"""Twitter source via Apify (apidojo/tweet-scraper or similar actor).

Apify offers a $5/month free tier which covers ~12k tweets/month — more than enough.
Sign up: https://apify.com -> Settings -> Integrations -> API -> create token.

This source runs the actor synchronously and returns parsed tweets.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

import requests

from .base import Tweet, TwitterSource

log = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"
TIMEOUT = 60


class ApifySource(TwitterSource):
    name = "apify"

    def __init__(self, token: str | None = None, actor_id: str = "apidojo/tweet-scraper") -> None:
        if not token:
            raise RuntimeError("APIFY_TOKEN is required when TWITTER_SOURCE=apify.")
        self.token = token
        # Actor IDs use ~ in the API path, e.g. apidojo~tweet-scraper.
        self.actor_path = actor_id.replace("/", "~")

    def fetch(self, accounts: list[str], lookback_hours: int) -> list[Tweet]:
        cutoff_ts = time.time() - lookback_hours * 3600
        # tweet-scraper accepts {twitterHandles, maxItems, sort, since, until}
        body = {
            "twitterHandles": accounts,
            "maxItems": max(20, len(accounts) * 5),
            "sort": "Latest",
            "tweetLanguage": "en",
        }
        url = f"{APIFY_BASE}/acts/{self.actor_path}/run-sync-get-dataset-items"
        log.info("apify: running actor %s for %d accounts", self.actor_path, len(accounts))
        resp = requests.post(
            url,
            params={"token": self.token},
            json=body,
            timeout=TIMEOUT,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Apify actor failed: HTTP {resp.status_code} {resp.text[:300]}")
        items = resp.json()
        if not isinstance(items, list):
            log.warning("apify: unexpected response shape: %r", type(items))
            return []
        out: list[Tweet] = []
        for item in items:
            tweet = self._normalize(item)
            if tweet is None:
                continue
            if tweet.created_ts and tweet.created_ts < cutoff_ts:
                continue
            out.append(tweet)
        log.info("apify: got %d tweets across %d accounts", len(out), len(accounts))
        return out

    @staticmethod
    def _normalize(item: dict) -> Tweet | None:
        # Common keys across Apify Twitter actors.
        tweet_id = str(
            item.get("id")
            or item.get("tweetId")
            or item.get("conversationId")
            or item.get("rest_id")
            or ""
        )
        text = (item.get("text") or item.get("full_text") or "").strip()
        author_obj = item.get("author") or item.get("user") or {}
        if isinstance(author_obj, dict):
            username = author_obj.get("userName") or author_obj.get("screen_name") or ""
        else:
            username = str(author_obj)
        username = (username or item.get("username") or "").lstrip("@")
        url = item.get("url") or item.get("twitterUrl") or ""
        if username and tweet_id and not url:
            url = f"https://twitter.com/{username}/status/{tweet_id}"
        if not (tweet_id and text and username):
            return None
        if item.get("isRetweet") or item.get("retweeted") or text.startswith("RT @"):
            return None
        created = item.get("createdAt") or item.get("created_at")
        ts = 0.0
        if isinstance(created, str):
            for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    ts = datetime.strptime(created, fmt).timestamp()
                    break
                except ValueError:
                    continue
        return Tweet(id=tweet_id, author=username, text=text, url=url, created_ts=ts)
