"""Common types & interface for Twitter sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Tweet:
    """A normalized tweet from any source."""

    id: str  # stable ID we use for dedup; the original status id when available
    author: str  # username, no @
    text: str  # plain text
    url: str  # canonical link to the tweet
    created_ts: float  # unix seconds; 0.0 if unknown


class TwitterSource(ABC):
    """Abstract Twitter source."""

    name: str = "base"

    @abstractmethod
    def fetch(self, accounts: list[str], lookback_hours: int) -> list[Tweet]:
        """Return tweets from `accounts` within the last `lookback_hours`."""
        raise NotImplementedError
