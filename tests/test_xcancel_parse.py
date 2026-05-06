"""Parse a known-shape xcancel/Nitter RSS feed without hitting the network."""
from __future__ import annotations

import feedparser

from src.sources.xcancel_source import XCancelSource

SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>aixbt_agent / @aixbt_agent</title>
    <description>Twitter feed for: @aixbt_agent.</description>
    <item>
      <title>watching $TOKEN</title>
      <description>watching $TOKEN flow into base. tvl up 24% in 6h.</description>
      <pubDate>Wed, 01 May 2024 12:00:00 GMT</pubDate>
      <link>https://xcancel.com/aixbt_agent/status/1234567890</link>
    </item>
    <item>
      <title>RT by @aixbt_agent: someone else</title>
      <description>RT body</description>
      <pubDate>Wed, 01 May 2024 11:00:00 GMT</pubDate>
      <link>https://xcancel.com/somebody/status/9999</link>
    </item>
  </channel>
</rss>
"""


def test_skips_retweets_and_parses_real():
    parsed = feedparser.parse(SAMPLE)
    tweets = XCancelSource._parse_feed(parsed, "aixbt_agent", cutoff_ts=0)
    assert len(tweets) == 1
    t = tweets[0]
    assert t.id == "1234567890"
    assert t.author == "aixbt_agent"
    assert "$TOKEN" in t.text
    assert t.url == "https://twitter.com/aixbt_agent/status/1234567890"
    assert t.created_ts > 0


def test_whitelist_message_detected():
    msg = """<?xml version="1.0"?><rss version="2.0"><channel>
      <title>RSS reader not yet whitelisted!</title>
      <description>token: bebbd13bce0453a392d0fc1da319b69f2d3242ccd39384accfe548aa8ff765b25b367d1c82439713cca8c3cf</description>
    </channel></rss>"""
    parsed = feedparser.parse(msg)
    tweets = XCancelSource._parse_feed(parsed, "aixbt_agent", cutoff_ts=0)
    assert tweets == []
