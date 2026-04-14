"""Game map representation with tileset support."""

from src.config import BiomeType
from src.data import TILE_INFO


class GameMap:
    """Represents a game map with its world, tileset, and tile HP."""

    def __init__(self, world: list[list[int]], tileset: str = "overland") -> None:
        """Initialize a game map.

        Args:
            world: 2D list of tile IDs
            tileset: String identifier for the tileset ("overland" or "cave")
        """
        self.world = world
        self.tileset = tileset
        self.biome: BiomeType = BiomeType.STANDARD
        self.rows = len(world)
        self.cols = len(world[0]) if world else 0

        # Initialize tile HP based on TILE_INFO
        self.tile_hp = [
            [TILE_INFO.get(self.world[r][c], {}).get("hp", 0) for c in range(self.cols)]
            for r in range(self.rows)
        ]

        # Enemy list — populated by cave environments; empty for overland
        self.enemies = []

        # Town cluster cache: maps (row, col) → cluster_size for HOUSE tiles
        self.town_clusters = {}

        # Sky-ladder quest state (home overland map only)
        self.sign_texts: dict[tuple[int, int], str] = {}  # (col, row) → text
        self.ladder_repaired: bool = False
        self.ladder_col: int = -1
        self.ladder_row: int = -1

        # Objects layer — ores, trees and other resource deposits layered on
        # top of the terrain grid.  None = empty cell.
        self.objects: list[list[int | None]] = [
            [None] * self.cols for _ in range(self.rows)
        ]
        self.object_hp: list[list[int]] = [[0] * self.cols for _ in range(self.rows)]

    def get_tile(self, row: int, col: int) -> int | None:
        """Get tile ID at position."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.world[row][col]
        return None

    def set_tile(self, row: int, col: int, tile_id: int) -> None:
        """Set tile ID at position."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.world[row][col] = tile_id
            self.tile_hp[row][col] = TILE_INFO.get(tile_id, {}).get("hp", 0)

    def get_tile_hp(self, row: int, col: int) -> int:
        """Get tile HP at position."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.tile_hp[row][col]
        return 0

    def set_tile_hp(self, row: int, col: int, hp: int) -> None:
        """Set tile HP at position."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.tile_hp[row][col] = hp

    # ------------------------------------------------------------------
    # Objects layer helpers
    # ------------------------------------------------------------------

    def get_object(self, row: int, col: int) -> int | None:
        """Return the object tile ID at *row*, *col*, or None if empty."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.objects[row][col]
        return None

    def set_object(self, row: int, col: int, tid: int) -> None:
        """Place object *tid* at *row*, *col* and initialise its HP."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.objects[row][col] = tid
            self.object_hp[row][col] = TILE_INFO.get(tid, {}).get("hp", 0)

    def clear_object(self, row: int, col: int) -> None:
        """Remove the object at *row*, *col*."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.objects[row][col] = None
            self.object_hp[row][col] = 0

    def get_object_hp(self, row: int, col: int) -> int:
        """Return current HP of the object at *row*, *col*."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.object_hp[row][col]
        return 0

    def set_object_hp(self, row: int, col: int, hp: int) -> None:
        """Set HP of the object at *row*, *col*."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.object_hp[row][col] = hp

    def get_tileset_color(self, tile_id: int) -> tuple[int, int, int]:
        """Get the color for a tile based on the current tileset.

        This allows different tilesets to render tiles differently.
        """
        tile_info = TILE_INFO.get(tile_id, {})
        base_color = tile_info.get("color", (100, 100, 100))

        # Adjust colors for cave tileset
        if self.tileset == "cave":
            # Make cave tiles darker/mossier
            r, g, b = base_color
            # Reduce brightness and add slight green tint for moss
            r = max(0, int(r * 0.7))
            g = max(0, int(g * 0.8))
            b = max(0, int(b * 0.6))
            return (r, g, b)

        # Adjust colors for underwater tileset: blue-green tint
        if self.tileset == "underwater":
            r, g, b = base_color
            r = max(0, int(r * 0.65))
            g = max(0, int(g * 0.9))
            b = min(255, int(b * 1.3))
            return (r, g, b)

        # Adjust colors for portal realm: dark stone with ancient purple tint
        if self.tileset == "portal_realm":
            r, g, b = base_color
            r = max(0, int(r * 0.8 + 15))
            g = max(0, int(g * 0.7))
            b = min(255, int(b * 1.1 + 20))
            return (r, g, b)

        # Biome cave tints
        if self.tileset == "cave_tundra":
            r, g, b = base_color
            r = max(0, int(r * 0.65 + 20))
            g = max(0, int(g * 0.75 + 20))
            b = min(255, int(b * 1.1 + 40))
            return (r, g, b)

        if self.tileset == "cave_volcano":
            r, g, b = base_color
            r = min(255, int(r * 0.9 + 40))
            g = max(0, int(g * 0.55))
            b = max(0, int(b * 0.45))
            return (r, g, b)

        if self.tileset == "cave_zombie":
            r, g, b = base_color
            r = max(0, int(r * 0.55))
            g = max(0, int(g * 0.75 + 15))
            b = max(0, int(b * 0.50))
            return (r, g, b)

        if self.tileset == "cave_desert":
            r, g, b = base_color
            r = min(255, int(r * 0.85 + 35))
            g = max(0, int(g * 0.75 + 15))
            b = max(0, int(b * 0.50))
            return (r, g, b)

        return base_color
