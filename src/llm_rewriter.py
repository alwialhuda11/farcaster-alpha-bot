"""Synthesize an aixbt_agent-style cast from one or more source tweets via OpenAI."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from openai import OpenAI

from .sources.base import Tweet

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
You are an alpha-focused crypto observer that writes posts in the style of @aixbt_agent on Twitter.

Voice & format rules:
- All lowercase. No hashtags. No emojis. No "follow me" / engagement bait.
- Short and punchy: 1 to 4 short sentences. Maximum 320 characters.
- Observational tone: "watching", "noticed", "tracking", "interesting", "real volume on", "flow into".
- Reference token tickers as $TOKEN (uppercase ticker, lowercase prose around it).
- Cite numbers/percentages/timeframes when present in the source ("up 24% in 6h", "tvl crossed 800m").
- Never invent numbers, prices, or facts that aren't in the source. If unsure, drop the number.
- Do not say "according to coindesk/decrypt/etc", do not quote, do not name news outlets or twitter handles. Synthesize the alpha as your own first-person observation.
- Don't mention news, articles, twitter, X, RSS, or that you're rewriting anything. You're not a bot in the prose.
- If the source has no real alpha (just opinion, recap, lifestyle, hot take, or pure speculation), return the single word: SKIP.
- If the source is non-English, translate the alpha to English and follow all rules above.

Output ONLY the post text or the literal word SKIP. No quotes, no preamble, no markdown.
"""


@dataclass(frozen=True)
class GenerationResult:
    text: str | None  # None if the model said SKIP
    model: str
    source_ids: list[str]


class LLMRewriter:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def synthesize(self, tweets: list[Tweet], max_length: int = 320) -> GenerationResult:
        if not tweets:
            raise ValueError("LLMRewriter.synthesize: no source items")
        # Build a compact source block for the prompt.
        lines = []
        for t in tweets[:5]:  # cap at 5 sources to keep token usage low
            lines.append(f"[{t.author}] {t.text}")
        user_msg = (
            "Source item(s) below (could be a tweet or a news headline+summary). "
            "Produce a single aixbt-style post that captures the alpha. "
            f"Hard cap: {max_length} characters.\n\n---\n" + "\n---\n".join(lines)
        )
        log.debug("LLM input: %s", user_msg)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=200,
        )
        text = (resp.choices[0].message.content or "").strip()
        # Remove surrounding quotes the model sometimes adds.
        if len(text) >= 2 and text[0] in "\"'" and text[-1] == text[0]:
            text = text[1:-1].strip()
        if text.upper() == "SKIP" or not text:
            return GenerationResult(text=None, model=self.model, source_ids=[t.id for t in tweets])
        # Hard truncate as a safety net.
        if len(text) > max_length:
            text = text[: max_length - 1].rstrip() + "…"
        return GenerationResult(text=text, model=self.model, source_ids=[t.id for t in tweets])
