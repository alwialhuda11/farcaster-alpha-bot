"""Entry point: pick fresh tweets, synthesize an aixbt-style cast, post to Farcaster.

Run modes:
- `python -m src.main` -> normal cron tick (probability-gated)
- `python -m src.main --force` -> always post (still respects active hours unless --any-time)
- `python -m src.main --dry-run` -> never call Neynar; just print
- `python -m src.main --any-time` -> bypass active hours window
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from datetime import UTC, datetime

from .config import Config
from .farcaster_client import FarcasterClient
from .llm_rewriter import LLMRewriter
from .sources import Tweet, build_source
from .state import load as load_state
from .state import mark_posted
from .state import save as save_state

log = logging.getLogger("farcaster_alpha_bot")


def _within_active_hours(now_utc_hour: int, start: int, end: int) -> bool:
    """Inclusive of start, exclusive of end. Wraps across midnight if start > end."""
    if start == end:
        return True
    if start < end:
        return start <= now_utc_hour < end
    return now_utc_hour >= start or now_utc_hour < end


def pick_tweet(tweets: list[Tweet], posted_ids: set[str]) -> Tweet | None:
    """Pick the freshest unposted tweet; tiebreak random among the top 3."""
    fresh = [t for t in tweets if t.id not in posted_ids]
    if not fresh:
        return None
    fresh.sort(key=lambda t: t.created_ts, reverse=True)
    top = fresh[:3]
    return random.choice(top)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Post crypto alpha to Farcaster.")
    p.add_argument("--force", action="store_true", help="Skip the random probability gate.")
    p.add_argument("--dry-run", action="store_true", help="Don't call Neynar; print instead.")
    p.add_argument("--any-time", action="store_true", help="Bypass the active-hours window.")
    p.add_argument(
        "-v", "--verbose", action="count", default=0, help="-v=info, -vv=debug"
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    level = logging.WARNING
    if args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose >= 1:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg = Config.load()
    if args.dry_run:
        cfg.dry_run = True
    cfg.require_posting_creds()

    if not cfg.accounts:
        log.error("No accounts configured. Edit config/accounts.yml.")
        return 2

    now = datetime.now(UTC)
    if not args.any_time and not _within_active_hours(
        now.hour, cfg.active_hours_start_utc, cfg.active_hours_end_utc
    ):
        log.warning(
            "Outside active hours (%02d:00-%02d:00 UTC), skipping. now=%02d UTC",
            cfg.active_hours_start_utc,
            cfg.active_hours_end_utc,
            now.hour,
        )
        return 0

    if not args.force and random.random() > cfg.post_probability:
        log.warning("Probability gate skip (P=%.2f).", cfg.post_probability)
        return 0

    # 1) Fetch tweets.
    src_kwargs: dict = {}
    if cfg.twitter_source == "apify":
        src_kwargs = {"token": cfg.apify_token, "actor_id": cfg.apify_actor_id}
    source = build_source(cfg.twitter_source, **src_kwargs)
    log.info("Fetching tweets via %s for %d accounts", source.name, len(cfg.accounts))
    tweets = source.fetch(cfg.accounts, cfg.lookback_hours)
    log.info("Fetched %d tweets total", len(tweets))
    if not tweets:
        log.warning("No tweets fetched. Check source credentials / whitelist.")
        return 1

    # 2) Pick a candidate.
    state = load_state()
    posted_ids = set(state.keys())
    chosen = pick_tweet(tweets, posted_ids)
    if chosen is None:
        log.warning("All %d tweets already posted. Nothing to do.", len(tweets))
        return 0
    log.info("Picked tweet %s by @%s: %s", chosen.id, chosen.author, chosen.text[:120])

    # 3) Synthesize via LLM.
    rewriter = LLMRewriter(api_key=cfg.openai_api_key, model=cfg.openai_model)
    result = rewriter.synthesize([chosen], max_length=cfg.max_length)
    if result.text is None:
        log.warning("LLM returned SKIP. Marking source as posted to avoid re-trying.")
        mark_posted(state, chosen.id)
        save_state(state)
        return 0
    if len(result.text) < cfg.min_length:
        log.warning(
            "LLM output too short (%d < %d). Skipping this tick.", len(result.text), cfg.min_length
        )
        return 0

    # 4) Publish.
    print("=" * 60)
    print(f"SOURCE @{chosen.author}: {chosen.text}")
    print("-" * 60)
    print(f"CAST ({len(result.text)} chars):")
    print(result.text)
    print("=" * 60)

    if cfg.dry_run:
        log.warning("DRY_RUN active — not calling Neynar.")
        return 0

    fc = FarcasterClient(api_key=cfg.neynar_api_key, signer_uuid=cfg.neynar_signer_uuid)
    response = fc.publish_cast(
        text=result.text,
        channel_id=cfg.farcaster_channel_id,
        idem=f"alpha-{chosen.id}-{int(time.time())}",
    )
    cast_hash = (response.get("cast") or {}).get("hash")
    log.warning("Posted cast hash=%s", cast_hash)

    # 5) Persist state.
    mark_posted(state, chosen.id)
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
