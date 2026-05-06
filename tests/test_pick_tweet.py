import random

from src.main import pick_tweet
from src.sources.base import Tweet


def make(tid: str, ts: float) -> Tweet:
    return Tweet(id=tid, author="u", text="t", url="", created_ts=ts)


def test_picks_among_freshest(monkeypatch):
    tweets = [make("a", 100.0), make("b", 90.0), make("c", 80.0), make("d", 50.0)]
    # Force deterministic random.choice -> first item.
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    chosen = pick_tweet(tweets, posted_ids=set())
    assert chosen is not None
    assert chosen.id == "a"


def test_skips_already_posted(monkeypatch):
    tweets = [make("a", 100.0), make("b", 90.0)]
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    chosen = pick_tweet(tweets, posted_ids={"a"})
    assert chosen is not None
    assert chosen.id == "b"


def test_returns_none_when_all_posted():
    tweets = [make("a", 100.0)]
    assert pick_tweet(tweets, posted_ids={"a"}) is None
