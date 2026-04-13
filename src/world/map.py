"""Game map representation with tileset support."""

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

        return base_color
