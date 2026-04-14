"""Creature type definitions.

Each entry in CREATURE_TYPES has:
    environment     -- CreatureEnvironment value
    speed           -- base wander speed (world-units/sec); +-15% variance applied at spawn
    size            -- visual size multiplier relative to TILE
    color_fn        -- callable() -> tuple[int,int,int]; called once per instance
    mount_speed_mult -- multiplier on player base speed while mounted
    mountable       -- whether a player can mount this creature
"""

from __future__ import annotations

import random
from enum import Enum
from typing import Callable


class CreatureEnvironment(Enum):
    OVERLAND = "overland"
    UNDERWATER = "underwater"


def _constant(color: tuple[int, int, int]) -> Callable[[], tuple[int, int, int]]:
    """Return a callable that always produces *color*."""
    return lambda: color


def _choice(colors: list[tuple[int, int, int]]) -> Callable[[], tuple[int, int, int]]:
    """Return a callable that picks a random entry from *colors* each call."""
    return lambda: random.choice(colors)


CREATURE_TYPES: dict[str, dict] = {
    # ------------------------------------------------------------------
    # Overland
    # ------------------------------------------------------------------
    "horse": {
        "environment": CreatureEnvironment.OVERLAND,
        "speed": 0.3,
        "size": 0.9,
        "color_fn": _choice([
            (139, 90, 43),   # chestnut
            (101, 67, 33),   # dark bay
            (180, 130, 70),  # palomino
            (60, 40, 25),    # near-black
        ]),
        "mount_speed_mult": 1.5,
        "mountable": True,
    },
    "grasshopper": {
        "environment": CreatureEnvironment.OVERLAND,
        "speed": 0.4,
        "size": 0.6,
        "color_fn": _choice([
            (80, 140, 60),   # grass green
            (110, 160, 50),  # bright lime
            (60, 100, 40),   # dark green
        ]),
        "mount_speed_mult": 1.8,
        "mountable": True,
    },
    # ------------------------------------------------------------------
    # Underwater
    # ------------------------------------------------------------------
    "dolphin": {
        "environment": CreatureEnvironment.UNDERWATER,
        "speed": 0.9,
        "size": 1.95,
        "color_fn": _constant((60, 130, 200)),
        "mount_speed_mult": 1.5,
        "mountable": True,
    },
    "fish": {
        "environment": CreatureEnvironment.UNDERWATER,
        "speed": 1.0,
        "size": 0.35,
        "color_fn": _choice([
            (240, 150, 30),
            (80, 200, 80),
            (180, 60, 200),
            (60, 200, 200),
        ]),
        "mount_speed_mult": 1.5,
        "mountable": False,
    },
    "jellyfish": {
        "environment": CreatureEnvironment.UNDERWATER,
        "speed": 0.4,
        "size": 0.40,
        "color_fn": _choice([
            (220, 80, 200),
            (180, 80, 255),
            (80, 200, 240),
        ]),
        "mount_speed_mult": 1.5,
        "mountable": False,
    },
}
