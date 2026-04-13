"""Base class for all game environments."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.world.map import GameMap


class BaseEnvironment:
    """Abstract base for environments (overland, cave, etc.).

    Each subclass defines how its map is generated and which enemies
    are appropriate for that environment.
    """

    def generate(self) -> "GameMap":
        """Generate and return a fully configured GameMap for this environment.

        Subclasses must implement this.  The returned GameMap may have
        extra attributes set (e.g. entrance_col for caves).
        """
        raise NotImplementedError

    def spawn_enemies(self, game_map: "GameMap") -> list:
        """Return a list of Enemy instances suitable for this environment.

        Args:
            game_map: The GameMap returned by generate(), in case spawn logic
                      needs to inspect tile layout.
        """
        raise NotImplementedError

    def spawn_creatures(self, game_map: "GameMap") -> list:
        """Return a list of Creature instances to populate this environment.

        Default implementation returns an empty list.  Override in subclasses
        that contain passive NPC animals (e.g. UnderwaterEnvironment for sea
        creatures, OverlandEnvironment for horses).
        """
        return []
