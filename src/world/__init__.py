"""World module: generation, collision, queries, and environments."""

from src.world.collision import (
    tile_at,
    pos_in_bounds,
    hits_blocking,
    out_of_bounds,
    try_spend,
    has_adjacent_house,
    compute_town_clusters,
    xp_for_level,
)
from src.world.generation import generate_world, generate_ocean_sector, spawn_enemies
from src.world.environments import OverlandEnvironment, CaveEnvironment

__all__ = [
    "tile_at",
    "pos_in_bounds",
    "hits_blocking",
    "out_of_bounds",
    "try_spend",
    "has_adjacent_house",
    "compute_town_clusters",
    "xp_for_level",
    "generate_world",
    "generate_ocean_sector",
    "spawn_enemies",
    "OverlandEnvironment",
    "CaveEnvironment",
]
