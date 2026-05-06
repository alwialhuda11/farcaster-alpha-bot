"""End-to-end orchestrator smoke test using fixture source + mocked LLM."""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


@pytest.fixture
def repo_env(tmp_path, monkeypatch):
    # Use a temporary state file so we don't pollute repo data/.
    monkeypatch.setattr("src.state.DEFAULT_PATH", tmp_path / "posted.json")
    # Force fixture source.
    monkeypatch.setenv("TWITTER_SOURCE", "fixture")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("NEYNAR_API_KEY", "test-nk")
    monkeypatch.setenv("NEYNAR_SIGNER_UUID", "test-signer")
    # Always-on active window, full probability so no skipping.
    monkeypatch.setenv("ACTIVE_HOURS_START_UTC", "0")
    monkeypatch.setenv("ACTIVE_HOURS_END_UTC", "0")
    monkeypatch.setenv("POST_PROBABILITY", "1.0")
    monkeypatch.setenv("MIN_LENGTH", "10")
    yield tmp_path


def test_dry_run_e2e(repo_env, monkeypatch, capsys):
    from src import main as main_mod
    from src.llm_rewriter import GenerationResult

    monkeypatch.setattr(
        sys, "argv", ["main", "--dry-run", "--force", "--any-time", "-vv"]
    )

    fake_result = GenerationResult(
        text="watching $HYPE - real volume up 38% wow. flow rotating from $JTO. interesting setup.",
        model="mock",
        source_ids=["demo-1"],
    )
    with patch("src.main.LLMRewriter") as MockLLM:
        MockLLM.return_value.synthesize.return_value = fake_result
        rc = main_mod.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "watching $HYPE" in out
    assert "SOURCE @" in out


def test_skip_when_llm_returns_skip(repo_env, monkeypatch):
    from src import main as main_mod
    from src.llm_rewriter import GenerationResult

    monkeypatch.setattr(
        sys, "argv", ["main", "--dry-run", "--force", "--any-time"]
    )

    skip_result = GenerationResult(text=None, model="mock", source_ids=[])
    with patch("src.main.LLMRewriter") as MockLLM:
        MockLLM.return_value.synthesize.return_value = skip_result
        rc = main_mod.main()
    assert rc == 0
    # State should now contain the skipped tweet so we don't retry it.
    from src import state

    s = state.load()
    # Whichever tweet was picked, it should now be marked posted.
    assert any(k.startswith("demo-") for k in s)
