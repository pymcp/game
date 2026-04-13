"""Overland (surface world) environment."""

from src.world.environments.base import BaseEnvironment
from src.world.generation import generate_world, spawn_enemies
from src.world.map import GameMap


class OverlandEnvironment(BaseEnvironment):
    """The overland surface world environment."""

    TILESET = "overland"

    def generate(self) -> GameMap:
        """Generate the overland world map."""
        world = generate_world()
        return GameMap(world, tileset=self.TILESET)

    def spawn_enemies(self, game_map: GameMap) -> list:
        """Spawn overland enemies on grass tiles away from spawn."""
        return spawn_enemies(game_map.world)
