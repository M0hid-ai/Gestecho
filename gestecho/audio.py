"""Microphone capture feeding the tap detector on a worker thread."""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable

import numpy as np

from .detector import DetectorConfig, TapDetector, TapEvent
from .devices import InputDevice

BLOCK = 480  # 10 ms at 48 kHz


class AudioCapture:
    """Opens an input stream; detection runs off the audio callback thread."""

    def __init__(self, on_event: Callable[[TapEvent], None], on_level: Callable[[float], None] | None = None):
        self.on_event = on_event
        self.on_level = on_level
        self.stream = None
        self.detector: TapDetector | None = None
        self.device: InputDevice | None = None
        self.channels = 1
        self.sample_rate = 48000
        self._queue: queue.Queue = queue.Queue(maxsize=400)
        self._worker: threading.Thread | None = None
        self._running = False
        self.dropped = 0

    @property
    def running(self) -> bool:
        return self._running

    def start(self, device: InputDevice, sensitivity: float = 6.0) -> None:
        import sounddevice as sd

        self.stop()
        self.device = device
        self.channels = min(device.channels, 2)
        self.sample_rate = 48000
        extra = sd.WasapiSettings(exclusive=False) if device.host == "Windows WASAPI" else None
        try:
            stream = sd.InputStream(
                device=device.index,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=BLOCK,
                dtype="float32",
                callback=self._callback,
                extra_settings=extra,
            )
        except sd.PortAudioError:
            # Shared-mode WASAPI only runs at the mixer rate.
            self.sample_rate = device.default_rate
            stream = sd.InputStream(
                device=device.index,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=int(self.sample_rate / 100),
                dtype="float32",
                callback=self._callback,
                extra_settings=extra,
            )
        self.detector = TapDetector(DetectorConfig(sample_rate=self.sample_rate, trigger_ratio=sensitivity))
        self._running = True
        self._worker = threading.Thread(target=self._drain, name="gestecho-dsp", daemon=True)
        self._worker.start()
        self.stream = stream
        stream.start()

    def stop(self) -> None:
        self._running = False
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            finally:
                self.stream = None
        if self._worker is not None:
            self._queue.put(None)
            self._worker.join(timeout=1.0)
            self._worker = None
        with self._queue.mutex:
            self._queue.queue.clear()

    def set_sensitivity(self, ratio: float) -> None:
        if self.detector:
            self.detector.set_sensitivity(ratio)

    def _callback(self, indata, frames, time_info, status) -> None:
        try:
            self._queue.put_nowait((indata.copy(), time.perf_counter()))
        except queue.Full:
            self.dropped += 1

    def _drain(self) -> None:
        last_level = 0.0
        while self._running:
            item = self._queue.get()
            if item is None:
                break
            block, _ = item
            for event in self.detector.process(block):
                self.on_event(event)
            if self.on_level is not None:
                now = time.perf_counter()
                if now - last_level > 0.05:
                    last_level = now
                    self.on_level(float(np.sqrt(np.mean(block**2))))
