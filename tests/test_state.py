from pathlib import Path

from src import state as st


def test_roundtrip(tmp_path: Path):
    p = tmp_path / "posted.json"
    s = st.load(p)
    assert s == {}
    st.mark_posted(s, "123")
    st.mark_posted(s, "456")
    st.save(s, p)

    s2 = st.load(p)
    assert set(s2.keys()) == {"123", "456"}


def test_caps_history(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(st, "MAX_HISTORY", 3)
    p = tmp_path / "posted.json"
    s = {}
    for i, ts in enumerate([1.0, 5.0, 3.0, 9.0, 2.0]):
        s[str(i)] = ts
    st.save(s, p)

    s2 = st.load(p)
    # should keep newest 3 by ts: ids 3 (9.0), 1 (5.0), 2 (3.0)
    assert set(s2.keys()) == {"3", "1", "2"}


def test_load_missing(tmp_path: Path):
    assert st.load(tmp_path / "nope.json") == {}


def test_load_invalid(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    assert st.load(p) == {}
