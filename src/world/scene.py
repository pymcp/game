"""MapScene: a GameMap paired with all entities/effects that live in it."""

from __future__ import annotations

import math
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
    from src.world.world_object import WorldObject


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
            "world_objects",
            "_obj_index",
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

        # WorldObjects layer: pixel-positioned discrete objects
        object.__setattr__(self, "world_objects", [])
        # Spatial index: (col, row) → index into world_objects list
        object.__setattr__(self, "_obj_index", {})

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

    # ------------------------------------------------------------------
    # WorldObjects API
    # ------------------------------------------------------------------

    def add_world_object(self, obj: "WorldObject") -> None:
        """Append *obj* to the world_objects list and update the spatial index."""
        world_objects: list = object.__getattribute__(self, "world_objects")
        idx_map: dict = object.__getattribute__(self, "_obj_index")
        idx = len(world_objects)
        world_objects.append(obj)
        idx_map[(obj.col, obj.row)] = idx

    def remove_world_object(self, obj_id: int) -> "WorldObject | None":
        """Remove the WorldObject with *obj_id* and rebuild the spatial index."""
        world_objects: list = object.__getattribute__(self, "world_objects")
        for i, obj in enumerate(world_objects):
            if obj.obj_id == obj_id:
                world_objects.pop(i)
                self._rebuild_obj_index()
                return obj
        return None

    def _rebuild_obj_index(self) -> None:
        """Rebuild the (col, row) → list-index mapping from scratch."""
        world_objects: list = object.__getattribute__(self, "world_objects")
        idx_map: dict = {}
        for i, obj in enumerate(world_objects):
            idx_map[(obj.col, obj.row)] = i
        object.__setattr__(self, "_obj_index", idx_map)

    def get_object_at(self, col: int, row: int) -> "WorldObject | None":
        """Return the WorldObject whose grid cell is *(col, row)*, or None."""
        idx_map: dict = object.__getattribute__(self, "_obj_index")
        world_objects: list = object.__getattribute__(self, "world_objects")
        idx = idx_map.get((col, row))
        if idx is None:
            return None
        return world_objects[idx]

    def objects_near(self, cx: float, cy: float, radius: float) -> list["WorldObject"]:
        """Return all WorldObjects whose centres are within *radius* pixels of
        *(cx, cy)*, sorted by distance (closest first)."""
        world_objects: list = object.__getattribute__(self, "world_objects")
        result = []
        for obj in world_objects:
            dist = obj.distance_to(cx, cy)
            if dist <= radius:
                result.append((dist, obj))
        result.sort(key=lambda t: t[0])
        return [obj for _, obj in result]

    def objects_in_viewport(
        self,
        cam_x: float,
        cam_y: float,
        view_w: int,
        view_h: int,
        margin: int = 64,
    ) -> list["WorldObject"]:
        """Return WorldObjects visible within the viewport rectangle (plus a small
        margin to avoid pop-in of tall sprites)."""
        world_objects: list = object.__getattribute__(self, "world_objects")
        x0 = cam_x - margin
        y0 = cam_y - margin
        x1 = cam_x + view_w + margin
        y1 = cam_y + view_h + margin
        return [obj for obj in world_objects if x0 <= obj.x <= x1 and y0 <= obj.y <= y1]

    def __repr__(self) -> str:
        game_map = object.__getattribute__(self, "map")
        return f"<MapScene map={game_map!r} enemies={len(self.enemies)} workers={len(self.workers)}>"
