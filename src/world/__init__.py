"""World module: generation, collision, and queries."""
from src.world.collision import (
    tile_at,
    pos_in_bounds,
    hits_blocking,
    out_of_bounds,
    try_spend,
    has_adjacent_house,
    xp_for_level,
)
from src.world.generation import generate_world, spawn_enemies

__all__ = [
    "tile_at",
    "pos_in_bounds",
    "hits_blocking",
    "out_of_bounds",
    "try_spend",
    "has_adjacent_house",
    "xp_for_level",
    "generate_world",
    "spawn_enemies",
]
