import json

from gestecho.evaluation import EvaluationSession, latest_report
from gestecho.zones import ALL_ZONES, Zone


def run_session(wrong_every: int = 0) -> EvaluationSession:
    s = EvaluationSession("abc")
    i = 0
    while not s.finished:
        zone = s.current_zone
        predicted = zone
        if wrong_every and i % wrong_every == 0:
            predicted = None
        s.record(predicted, 0.9, 120.0 + i, None if predicted else "ambiguous")
        i += 1
    return s


def test_order_and_totals():
    s = EvaluationSession("abc")
    assert s.total == 60
    seen = []
    while not s.finished:
        seen.append(s.current_zone)
        s.record(s.current_zone, 1.0, 10)
    assert seen == [z for z in ALL_ZONES for _ in range(15)]
    assert s.current_zone is None


def test_perfect_run_passes():
    report = run_session().report()
    assert report.accuracy == 1.0
    assert report.passed
    assert report.confusion[Zone.LEFT_REAR.value][Zone.LEFT_REAR.value] == 15


def test_rejections_count_as_wrong():
    report = run_session(wrong_every=4).report()
    assert report.rejected == 15
    assert report.accuracy == 0.75
    assert not report.passed
    assert sum(row["rejected"] for row in report.confusion.values()) == 15


def test_save_and_restore(tmp_path):
    report = run_session().report()
    json_path, csv_path = report.save(tmp_path)
    assert csv_path.read_text().count("\n") == 61
    saved = latest_report("abc", tmp_path)
    assert saved["accuracy"] == 1.0
    assert json.loads(json_path.read_text())["passed"] is True
    assert latest_report("other", tmp_path) is None
