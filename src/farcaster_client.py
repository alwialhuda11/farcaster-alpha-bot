"""Post casts to Farcaster via the Neynar API."""
from __future__ import annotations

import logging
import uuid

import requests

log = logging.getLogger(__name__)

NEYNAR_BASE = "https://api.neynar.com"
TIMEOUT = 30


class FarcasterClient:
    """Thin wrapper around POST /v2/farcaster/cast."""

    def __init__(self, api_key: str, signer_uuid: str) -> None:
        if not api_key:
            raise ValueError("FarcasterClient: api_key is required")
        if not signer_uuid:
            raise ValueError("FarcasterClient: signer_uuid is required")
        self.api_key = api_key
        self.signer_uuid = signer_uuid

    def publish_cast(
        self,
        text: str,
        channel_id: str | None = None,
        embeds: list[dict] | None = None,
        idem: str | None = None,
    ) -> dict:
        body: dict = {
            "signer_uuid": self.signer_uuid,
            "text": text,
            "idem": idem or uuid.uuid4().hex[:32],
        }
        if channel_id:
            body["channel_id"] = channel_id
        if embeds:
            body["embeds"] = embeds[:2]  # Neynar caps at 2
        url = f"{NEYNAR_BASE}/v2/farcaster/cast"
        log.info("Neynar publish_cast: text_len=%d channel=%s", len(text), channel_id or "<home>")
        resp = requests.post(
            url,
            json=body,
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "x-api-key": self.api_key,
            },
            timeout=TIMEOUT,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Neynar publish_cast failed: HTTP {resp.status_code} {resp.text[:500]}"
            )
        return resp.json()
