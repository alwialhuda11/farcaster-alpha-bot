"""Config loading from env + YAML."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass
class Config:
    # Farcaster
    neynar_api_key: str
    neynar_signer_uuid: str
    farcaster_channel_id: str | None

    # LLM
    openai_api_key: str
    openai_model: str

    # Twitter source
    twitter_source: str
    apify_token: str | None
    apify_actor_id: str

    # Behavior
    post_probability: float
    active_hours_start_utc: int
    active_hours_end_utc: int
    min_length: int
    max_length: int
    lookback_hours: int
    dry_run: bool

    # Accounts (used by xcancel / apify sources)
    accounts: list[str] = field(default_factory=list)
    # News feeds (used by news_rss source). Each entry: (name, url).
    feeds: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def load(cls, repo_root: Path | None = None) -> Config:
        load_dotenv()
        repo_root = repo_root or Path(__file__).resolve().parents[1]
        accounts_file = repo_root / "config" / "accounts.yml"
        accounts: list[str] = []
        feeds: list[tuple[str, str]] = []
        if accounts_file.exists():
            with accounts_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            accounts = [str(a).strip().lstrip("@") for a in data.get("accounts", []) if a]
            for entry in data.get("feeds", []) or []:
                if isinstance(entry, dict) and entry.get("url"):
                    feeds.append(
                        (str(entry.get("name") or entry["url"]).strip(), str(entry["url"]).strip())
                    )

        return cls(
            neynar_api_key=os.getenv("NEYNAR_API_KEY", "").strip(),
            neynar_signer_uuid=os.getenv("NEYNAR_SIGNER_UUID", "").strip(),
            farcaster_channel_id=(os.getenv("FARCASTER_CHANNEL_ID", "").strip() or None),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
            twitter_source=os.getenv("TWITTER_SOURCE", "news_rss").strip().lower() or "news_rss",
            apify_token=(os.getenv("APIFY_TOKEN", "").strip() or None),
            apify_actor_id=os.getenv("APIFY_ACTOR_ID", "apidojo/tweet-scraper").strip(),
            post_probability=_float("POST_PROBABILITY", 0.5),
            active_hours_start_utc=_int("ACTIVE_HOURS_START_UTC", 2),
            active_hours_end_utc=_int("ACTIVE_HOURS_END_UTC", 20),
            min_length=_int("MIN_LENGTH", 80),
            max_length=_int("MAX_LENGTH", 320),
            lookback_hours=_int("LOOKBACK_HOURS", 24),
            dry_run=_bool("DRY_RUN", False),
            accounts=accounts,
            feeds=feeds,
        )

    def require_posting_creds(self) -> None:
        missing: list[str] = []
        if not self.dry_run:
            if not self.neynar_api_key:
                missing.append("NEYNAR_API_KEY")
            if not self.neynar_signer_uuid:
                missing.append("NEYNAR_SIGNER_UUID")
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if missing:
            raise RuntimeError(
                f"Missing required env vars: {', '.join(missing)}. "
                "See .env.example for the full list."
            )

    def needs_accounts(self) -> bool:
        """True only for sources that scrape Twitter accounts."""
        return self.twitter_source in ("xcancel", "apify")
