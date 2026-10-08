"""The four fixed desk zones around the laptop."""

from __future__ import annotations

from enum import Enum


class Zone(str, Enum):
    LEFT_REAR = "left_rear"
    RIGHT_REAR = "right_rear"
    LEFT_FRONT = "left_front"
    RIGHT_FRONT = "right_front"

    @property
    def label(self) -> str:
        return {
            Zone.LEFT_REAR: "Left Rear",
            Zone.RIGHT_REAR: "Right Rear",
            Zone.LEFT_FRONT: "Left Front",
            Zone.RIGHT_FRONT: "Right Front",
        }[self]

    @property
    def index(self) -> int:
        return ALL_ZONES.index(self)


ALL_ZONES: list[Zone] = [Zone.LEFT_REAR, Zone.RIGHT_REAR, Zone.LEFT_FRONT, Zone.RIGHT_FRONT]
