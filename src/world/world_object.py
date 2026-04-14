"""WorldObject — a discrete placeable object with a world-space pixel position.

WorldObjects live in ``MapScene.world_objects`` rather than the terrain grid,
which means they can be placed at arbitrary float coordinates and repositioned
at runtime.  They carry a hitbox radius for movement collision and an interact
radius for E-key interaction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # avoid circular imports; callers import TILE_INFO directly

# ---------------------------------------------------------------------------
# Module-level ID counter (reset safe across test runs via _reset_counter)
# ---------------------------------------------------------------------------
_next_obj_id: int = 0


def _alloc_id() -> int:
    global _next_obj_id
    _next_obj_id += 1
    return _next_obj_id


def _reset_counter(value: int = 0) -> None:
    """Reset the ID counter.  Called by save/load to resume after the highest
    persisted id so newly generated objects never clash with loaded ones."""
    global _next_obj_id
    _next_obj_id = value


# ---------------------------------------------------------------------------
# WorldObject dataclass
# ---------------------------------------------------------------------------


@dataclass
class WorldObject:
    """A discrete placeable world object.

    Attributes:
        tile_id:         Tile-type constant (STONE, SIGN, CAVE_EXIT, …).
        x:               World-space pixel centre X (float → arbitrary placement).
        y:               World-space pixel centre Y.
        hp:              Current hit points (0 for non-mineable objects).
        hitbox_radius:   Pixel radius for movement collision.  0 → walkable through.
        interact_radius: Pixel radius for E-key interaction.  0 → not interactable.
        obj_id:          Stable integer identity; unique within the app lifetime.
    """

    tile_id: int
    x: float
    y: float
    hp: int
    hitbox_radius: float
    interact_radius: float
    obj_id: int = field(default_factory=_alloc_id)

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def distance_to(self, cx: float, cy: float) -> float:
        """Euclidean distance from this object's centre to *(cx, cy)*."""
        return math.hypot(self.x - cx, self.y - cy)

    def blocks_movement(self, cx: float, cy: float, mover_radius: float) -> bool:
        """Return True if a circle at *(cx, cy)* with *mover_radius* overlaps
        this object's hitbox."""
        if self.hitbox_radius <= 0:
            return False
        return self.distance_to(cx, cy) < mover_radius + self.hitbox_radius

    def in_interact_range(self, cx: float, cy: float) -> bool:
        """Return True if *(cx, cy)* is within this object's interact radius."""
        if self.interact_radius <= 0:
            return False
        return self.distance_to(cx, cy) <= self.interact_radius

    # ------------------------------------------------------------------
    # Tile-grid helpers
    # ------------------------------------------------------------------

    @property
    def col(self) -> int:
        """Tile column of this object's centre (integer, 0-based)."""
        from src.config import TILE

        return int(self.x) // TILE

    @property
    def row(self) -> int:
        """Tile row of this object's centre (integer, 0-based)."""
        from src.config import TILE

        return int(self.y) // TILE

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_tile(
        cls,
        tile_id: int,
        col: int,
        row: int,
        *,
        obj_id: int | None = None,
    ) -> "WorldObject":
        """Create a WorldObject centred on grid cell *(col, row)*.

        Reads ``hitbox_radius``, ``interact_radius``, and ``hp`` from
        ``TILE_INFO``.  Falls back to 0 for any missing key.

        Args:
            tile_id:  The tile-type constant.
            col:      Grid column.
            row:      Grid row.
            obj_id:   Explicit id (e.g. when restoring from save).  When
                      *None* a fresh id is allocated.
        """
        from src.config import TILE
        from src.data.tiles import TILE_INFO

        info = TILE_INFO.get(tile_id, {})
        cx = col * TILE + TILE // 2
        cy = row * TILE + TILE // 2
        hp = info.get("hp", 0)
        hitbox_radius = float(info.get("hitbox_radius", 0))
        interact_radius = float(info.get("interact_radius", 0))

        if obj_id is not None:
            obj = cls.__new__(cls)
            # Bypass default_factory so we use the provided id without
            # incrementing the counter.
            object.__setattr__(obj, "tile_id", tile_id)
            object.__setattr__(obj, "x", float(cx))
            object.__setattr__(obj, "y", float(cy))
            object.__setattr__(obj, "hp", hp)
            object.__setattr__(obj, "hitbox_radius", hitbox_radius)
            object.__setattr__(obj, "interact_radius", interact_radius)
            object.__setattr__(obj, "obj_id", obj_id)
            return obj

        return cls(
            tile_id=tile_id,
            x=float(cx),
            y=float(cy),
            hp=hp,
            hitbox_radius=hitbox_radius,
            interact_radius=interact_radius,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict."""
        return {
            "tile_id": self.tile_id,
            "x": self.x,
            "y": self.y,
            "hp": self.hp,
            "hitbox_radius": self.hitbox_radius,
            "interact_radius": self.interact_radius,
            "obj_id": self.obj_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WorldObject":
        """Restore from a serialised dict.

        The stored ``obj_id`` is re-used; the module counter is *not*
        advanced here — callers should call ``_reset_counter`` with the
        maximum loaded id after deserialising all objects.
        """
        obj_id = int(d["obj_id"])
        obj = cls.__new__(cls)
        object.__setattr__(obj, "tile_id", int(d["tile_id"]))
        object.__setattr__(obj, "x", float(d["x"]))
        object.__setattr__(obj, "y", float(d["y"]))
        object.__setattr__(obj, "hp", int(d["hp"]))
        object.__setattr__(obj, "hitbox_radius", float(d["hitbox_radius"]))
        object.__setattr__(obj, "interact_radius", float(d["interact_radius"]))
        object.__setattr__(obj, "obj_id", obj_id)
        return obj
