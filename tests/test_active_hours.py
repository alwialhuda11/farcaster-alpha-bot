from src.main import _within_active_hours


def test_simple_window():
    assert _within_active_hours(5, 2, 20)
    assert _within_active_hours(2, 2, 20)
    assert not _within_active_hours(20, 2, 20)
    assert not _within_active_hours(1, 2, 20)


def test_wrap_midnight():
    # 22:00 - 04:00 window
    assert _within_active_hours(23, 22, 4)
    assert _within_active_hours(0, 22, 4)
    assert _within_active_hours(3, 22, 4)
    assert not _within_active_hours(4, 22, 4)
    assert not _within_active_hours(12, 22, 4)


def test_full_day():
    # start == end means always active
    for h in range(24):
        assert _within_active_hours(h, 0, 0)
