"""Overland (surface world) environment."""

import random

from src.config import GRASS, TILE
from src.world.environments.base import BaseEnvironment
from src.world.generation import generate_world, spawn_enemies
from src.world.map import GameMap

# Border margin — avoid spawning horses on map-edge tiles
_EDGE_MARGIN = 4


class OverlandEnvironment(BaseEnvironment):
    """The overland surface world environment."""

    TILESET = "overland"

    def __init__(self, map_key: str | tuple = "overland") -> None:
        self.map_key = map_key

    def generate(self) -> GameMap:
        """Generate the overland world map."""
        world = generate_world()
        return GameMap(world, tileset=self.TILESET)

    def spawn_enemies(self, game_map: GameMap) -> list:
        """Spawn overland enemies on grass tiles away from spawn."""
        return spawn_enemies(game_map.world)

    def spawn_creatures(self, game_map: GameMap) -> list:
        """Spawn 2–4 horses on GRASS tiles at least 4 tiles from the map edge."""
        from src.entities.overland_creature import OverlandCreature

        rows = game_map.rows
        cols = game_map.cols
        rng = random.Random()

        candidates = [
            (c, r)
            for r in range(_EDGE_MARGIN, rows - _EDGE_MARGIN)
            for c in range(_EDGE_MARGIN, cols - _EDGE_MARGIN)
            if game_map.world[r][c] == GRASS
        ]

        if not candidates:
            return []

        creatures = []

        def _place_horse(col: int, row: int) -> None:
            creatures.append(
                OverlandCreature(
                    col * TILE + TILE // 2,
                    row * TILE + TILE // 2,
                    kind="horse",
                    home_map=self.map_key,
                )
            )

        # Guarantee exactly one horse by picking unconditionally from the full list
        first_col, first_row = rng.choice(candidates)
        _place_horse(first_col, first_row)
        # Remove tiles too close to the first horse for the remaining placements
        remaining = [
            pos for pos in candidates
            if abs(pos[0] - first_col) + abs(pos[1] - first_row) > 6
        ]
        # Try to add up to 3 more, each separated from all previous
        for _ in range(rng.randint(0, 3)):
            if not remaining:
                break
            col, row = rng.choice(remaining)
            _place_horse(col, row)
            remaining = [
                pos for pos in remaining
                if abs(pos[0] - col) + abs(pos[1] - row) > 6
            ]

        return creatures
