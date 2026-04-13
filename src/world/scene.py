"""MapScene: a GameMap paired with all entities/effects that live in it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.world.map import GameMap
    from src.entities.worker import Worker
    from src.entities.pet import Pet
    from src.entities.creature import Creature
    from src.entities.enemy import Enemy
    from src.entities.projectile import Projectile
    from src.effects.particle import Particle
    from src.effects.floating_text import FloatingText


class MapScene:
    """Wraps a GameMap and co-locates every entity/effect belonging to that map.

    Attribute access falls through to the underlying GameMap for anything that
    isn't one of the scene-owned attributes, so existing code that accesses
    tile data (world, tile_hp, tileset, rows, cols, …) via the map value
    continues to work unchanged.
    """

    _SCENE_ATTRS: frozenset[str] = frozenset(
        {
            "map",
            "enemies",
            "workers",
            "pets",
            "creatures",
            "projectiles",
            "particles",
            "floats",
        }
    )

    def __init__(self, game_map: "GameMap") -> None:
        # Bypass our own __setattr__ so we write directly to the instance dict.
        object.__setattr__(self, "map", game_map)

        # Transfer any enemies already attached to the raw GameMap.
        existing_enemies: list = list(getattr(game_map, "enemies", []))
        # Clear from the raw map so they live only here.
        try:
            game_map.enemies = []  # type: ignore[assignment]
        except (AttributeError, TypeError):
            pass
        object.__setattr__(self, "enemies", existing_enemies)

        for attr in (
            "workers",
            "pets",
            "creatures",
            "projectiles",
            "particles",
            "floats",
        ):
            object.__setattr__(self, attr, [])

    # ------------------------------------------------------------------
    # Proxy: unknown attribute reads go to the underlying GameMap.
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        # Called only when normal attribute lookup has already failed.
        try:
            game_map = object.__getattribute__(self, "map")
        except AttributeError:
            raise AttributeError(f"MapScene has no attribute '{name}'")
        return getattr(game_map, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in MapScene._SCENE_ATTRS:
            object.__setattr__(self, name, value)
        else:
            game_map = object.__getattribute__(self, "map")
            setattr(game_map, name, value)

    def __repr__(self) -> str:
        game_map = object.__getattribute__(self, "map")
        return f"<MapScene map={game_map!r} enemies={len(self.enemies)} workers={len(self.workers)}>"
