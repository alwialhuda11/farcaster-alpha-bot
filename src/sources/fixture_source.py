"""Fixture source: read tweets from data/fixture_tweets.json.

Useful for local testing without any network calls. Format:

```json
[
  {"id": "1", "author": "aixbt_agent", "text": "watching $TOKEN ...",
   "url": "https://twitter.com/aixbt_agent/status/1", "created_ts": 0}
]
```
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .base import Tweet, TwitterSource


class FixtureSource(TwitterSource):
    name = "fixture"

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            path = Path(__file__).resolve().parents[2] / "data" / "fixture_tweets.json"
        self.path = Path(path)

    def fetch(self, accounts: list[str], lookback_hours: int) -> list[Tweet]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        cutoff_ts = time.time() - lookback_hours * 3600
        out: list[Tweet] = []
        for item in data:
            ts = float(item.get("created_ts") or 0.0)
            if ts and ts < cutoff_ts:
                continue
            author = str(item.get("author", "")).lstrip("@")
            if accounts and author.lower() not in {a.lower() for a in accounts}:
                continue
            out.append(
                Tweet(
                    id=str(item["id"]),
                    author=author,
                    text=str(item["text"]),
                    url=str(item.get("url", "")),
                    created_ts=ts,
                )
            )
        return out
