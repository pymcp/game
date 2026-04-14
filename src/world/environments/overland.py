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
        world, objects = generate_world()
        game_map = GameMap(world, tileset=self.TILESET)
        for r in range(game_map.rows):
            for c in range(game_map.cols):
                if objects[r][c] is not None:
                    game_map.set_object(r, c, objects[r][c])
        return game_map

    def spawn_enemies(self, game_map: GameMap) -> list:
        """Spawn overland enemies on grass tiles away from spawn."""
        return spawn_enemies(game_map.world)

    def spawn_creatures(self, game_map: GameMap) -> list:
        """Spawn 2–4 horses and 1–2 grasshoppers on GRASS tiles."""
        from src.entities.creature import Creature

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

        def _place(col: int, row: int, kind: str) -> None:
            creatures.append(
                Creature(
                    col * TILE + TILE // 2,
                    row * TILE + TILE // 2,
                    kind,
                    self.map_key,
                )
            )

        # --- Horses (1 guaranteed + up to 3 more) ---
        first_col, first_row = rng.choice(candidates)
        _place(first_col, first_row, "horse")
        remaining = [
            pos
            for pos in candidates
            if abs(pos[0] - first_col) + abs(pos[1] - first_row) > 6
        ]
        for _ in range(rng.randint(0, 3)):
            if not remaining:
                break
            col, row = rng.choice(remaining)
            _place(col, row, "horse")
            remaining = [
                pos for pos in remaining if abs(pos[0] - col) + abs(pos[1] - row) > 6
            ]

        # --- Grasshoppers (1–2) ---
        grass_pool = [
            p
            for p in candidates
            if p not in [(c.x // TILE, c.y // TILE) for c in creatures]
        ]
        for _ in range(rng.randint(1, 20)):
            if not grass_pool:
                break
            col, row = rng.choice(grass_pool)
            _place(col, row, "grasshopper")
            grass_pool = [
                pos for pos in grass_pool if abs(pos[0] - col) + abs(pos[1] - row) > 4
            ]

        return creatures
