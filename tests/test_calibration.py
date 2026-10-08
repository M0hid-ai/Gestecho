import numpy as np

from gestecho.calibration import CalibrationSession
from gestecho.zones import ALL_ZONES


def test_walks_zones_in_order():
    s = CalibrationSession()
    for zone in ALL_ZONES:
        assert s.current_zone == zone
        for _ in range(10):
            ok, _ = s.offer(np.zeros(3))
            assert ok
    assert s.complete
    assert s.accepted_total == 40


def test_rejects_bad_taps_with_guidance():
    s = CalibrationSession()
    ok, msg = s.offer(np.zeros(3), quality="weak")
    assert not ok and "firmer" in msg
    ok, msg = s.offer(np.zeros(3), quality="clipped")
    assert not ok and "lighter" in msg
    ok, msg = s.offer(np.zeros(3), rejection="sustained")
    assert not ok and "quiet" in msg
    assert s.accepted_total == 0


def test_undo_and_redo_zone():
    s = CalibrationSession(taps_per_zone=2)
    for _ in range(4):
        s.offer(np.zeros(3))
    assert s.current_zone == ALL_ZONES[2]
    assert s.undo() == ALL_ZONES[1]
    assert s.current_zone == ALL_ZONES[1]
    s.offer(np.zeros(3))
    s.redo_zone(ALL_ZONES[0])
    assert s.current_zone == ALL_ZONES[0]
    assert ALL_ZONES[0] not in s.order


def test_consistency_report(calibration):
    x, y = calibration
    s = CalibrationSession()
    for row, label in zip(x, y):
        assert s.current_zone == ALL_ZONES[label]
        s.offer(row)
    report = s.consistency()
    assert report.overall == 1.0
