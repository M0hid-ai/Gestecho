import numpy as np

from gestecho import synth
from gestecho.detector import TapDetector, is_sustained
from gestecho.zones import ALL_ZONES


def feed(detector, audio, block=480):
    events = []
    for i in range(0, len(audio), block):
        events += detector.process(audio[i : i + block])
    return events


def test_finds_every_tap_near_its_onset():
    zones = [ALL_ZONES[i % 4] for i in range(16)]
    audio, onsets = synth.sequence(zones)
    events = feed(TapDetector(), audio)
    assert len(events) == len(onsets)
    for event, onset in zip(events, onsets):
        assert abs(event.onset_index - onset) <= 256
        assert event.accepted
        assert event.samples.shape == (4320, 2)


def test_block_size_does_not_matter():
    audio, _ = synth.sequence(ALL_ZONES * 2)
    a = feed(TapDetector(), audio, 480)
    b = feed(TapDetector(), audio, 1024)
    assert [e.onset_index for e in a] == [e.onset_index for e in b]


def test_quiet_room_produces_nothing():
    assert feed(TapDetector(), synth.noise(3.0)) == []


def test_nothing_fires_while_learning_the_room():
    audio = synth.tap(ALL_ZONES[0])
    assert feed(TapDetector(), audio) == []


def test_abrupt_tone_is_flagged_sustained():
    tone = synth.tone(0.5, freq=1500.0, amplitude=0.3)
    audio = np.concatenate([synth.noise(1.0), tone, synth.noise(0.5)])
    events = feed(TapDetector(), audio)
    assert events, "the tone onset should trigger"
    assert all(e.rejection == "sustained" for e in events)


def test_sustained_gate_shapes():
    tap = np.vstack([np.zeros((480, 1)), synth.tap(ALL_ZONES[0], channels=1)])[:4320]
    assert not is_sustained(tap, 480, 48000)
    tone = np.vstack([np.zeros((480, 1)), synth.tone(0.1, channels=1)])[:4320]
    assert is_sustained(tone, 480, 48000)


def test_quality_flags():
    loud = synth.sequence([ALL_ZONES[0]])[0]
    loud[48000:] *= 20
    events = feed(TapDetector(), loud)
    assert events and events[0].quality == "clipped"


def test_mono_input_supported():
    audio, onsets = synth.sequence(ALL_ZONES, channels=1)
    events = feed(TapDetector(), audio[:, 0])
    assert len(events) == len(onsets)
    assert events[0].samples.shape[1] == 1
