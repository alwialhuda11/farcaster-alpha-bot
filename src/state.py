"""Track which source tweets we've already posted, so we don't repeat."""
from __future__ import annotations

import json
import time
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "posted.json"
MAX_HISTORY = 5000  # cap state file size


def load(path: Path | None = None) -> dict[str, float]:
    """Load {tweet_id: timestamp} mapping. Missing/invalid file -> empty dict."""
    path = path or DEFAULT_PATH
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): float(v) for k, v in data.items()}
    except (json.JSONDecodeError, ValueError, OSError):
        pass
    return {}


def save(state: dict[str, float], path: Path | None = None) -> None:
    path = path or DEFAULT_PATH
    # Keep newest MAX_HISTORY entries.
    if len(state) > MAX_HISTORY:
        keep = sorted(state.items(), key=lambda kv: kv[1], reverse=True)[:MAX_HISTORY]
        state = dict(keep)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def mark_posted(state: dict[str, float], tweet_id: str) -> None:
    state[str(tweet_id)] = time.time()
