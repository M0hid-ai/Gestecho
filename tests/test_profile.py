import json

import pytest

from gestecho.actions import Action
from gestecho.profile import Profile, ProfileStore, Sample
from gestecho.zones import ALL_ZONES, Zone


def make_profile(calibration) -> Profile:
    x, y = calibration
    p = Profile(name="Home desk", channels=2)
    p.samples = [Sample(ALL_ZONES[label], row.tolist()) for row, label in zip(x, y)]
    p.actions[Zone.LEFT_REAR] = Action("open_url", "https://example.com")
    return p


def test_roundtrip(tmp_path, calibration):
    store = ProfileStore(tmp_path)
    p = make_profile(calibration)
    path = store.save(p)
    assert path.name.startswith("home-desk-")
    loaded = store.get(p.id)
    assert loaded.name == "Home desk"
    assert loaded.counts() == {z: 10 for z in ALL_ZONES}
    assert loaded.actions[Zone.LEFT_REAR].value == "https://example.com"
    assert loaded.train().trained


def test_resave_keeps_one_file(tmp_path, calibration):
    store = ProfileStore(tmp_path)
    p = make_profile(calibration)
    store.save(p)
    p.name = "Renamed"
    store.save(p)
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_incompatible_profile_skipped(tmp_path, calibration):
    store = ProfileStore(tmp_path)
    p = make_profile(calibration)
    path = store.save(p)
    raw = json.loads(path.read_text())
    raw["schema"] = 999
    path.write_text(json.dumps(raw))
    assert store.load_all() == []
    with pytest.raises(ValueError):
        Profile.from_dict(raw)


def test_corrupt_file_ignored(tmp_path):
    (tmp_path / "broken.json").write_text("{nope")
    assert ProfileStore(tmp_path).load_all() == []


def test_delete(tmp_path, calibration):
    store = ProfileStore(tmp_path)
    p = make_profile(calibration)
    store.save(p)
    store.delete(p)
    assert store.get(p.id) is None
