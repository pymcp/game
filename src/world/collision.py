"""Collision detection and world queries."""

from src.config import TILE, WORLD_COLS, WORLD_ROWS
from src.data import BLOCKING_TILES


def tile_at(world, wx, wy):
    """Get tile ID at world position, or -1 if out of bounds."""
    col = int(wx) // TILE
    row = int(wy) // TILE
    world_rows = len(world)
    world_cols = len(world[0]) if world_rows > 0 else 0
    if col < 0 or col >= world_cols or row < 0 or row >= world_rows:
        return -1
    return world[row][col]


def pos_in_bounds_world(wx, wy, world):
    """Check if world position is within the given world's bounds."""
    col = int(wx) // TILE
    row = int(wy) // TILE
    world_rows = len(world)
    world_cols = len(world[0]) if world_rows > 0 else 0
    return 0 <= col < world_cols and 0 <= row < world_rows


def pos_in_bounds(wx, wy):
    """Check if world position is within default world bounds (overland)."""
    col = int(wx) // TILE
    row = int(wy) // TILE
    return 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS


def hits_blocking(world, cx, cy, half):
    """Check if a circle (center cx,cy, radius half) hits any blocking tile."""
    for ox in (-half, half):
        for oy in (-half, half):
            if tile_at(world, cx + ox, cy + oy) in BLOCKING_TILES:
                return True
    return False


def out_of_bounds(cx, cy, half, world=None):
    """Check if a circle would leave the world bounds."""
    for ox in (-half, half):
        for oy in (-half, half):
            if world is not None:
                if not pos_in_bounds_world(cx + ox, cy + oy, world):
                    return True
            else:
                if not pos_in_bounds(cx + ox, cy + oy):
                    return True
    return False


def try_spend(inventory, cost):
    """Deduct items from inventory if affordable. Returns True on success."""
    if not all(inventory.get(k, 0) >= v for k, v in cost.items()):
        return False
    for k, v in cost.items():
        inventory[k] -= v
        if inventory[k] <= 0:
            del inventory[k]
    return True


def has_adjacent_house(world, col, row):
    """Check if this tile has a HOUSE neighbor."""
    from src.config import HOUSE

    for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nc, nr = col + dc, row + dr
        if 0 <= nc < WORLD_COLS and 0 <= nr < WORLD_ROWS:
            if world[nr][nc] == HOUSE:
                return True
    return False


def compute_town_clusters(world):
    """BFS flood-fill to find all connected HOUSE clusters.

    Returns a dict mapping (row, col) → cluster_size for every HOUSE tile.
    """
    from src.config import HOUSE

    rows = len(world)
    cols = len(world[0]) if rows > 0 else 0
    visited = set()
    result = {}

    for start_r in range(rows):
        for start_c in range(cols):
            if world[start_r][start_c] == HOUSE and (start_r, start_c) not in visited:
                cluster = []
                queue = [(start_r, start_c)]
                visited.add((start_r, start_c))
                while queue:
                    r, c = queue.pop(0)
                    cluster.append((r, c))
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if (
                            0 <= nr < rows
                            and 0 <= nc < cols
                            and world[nr][nc] == HOUSE
                            and (nr, nc) not in visited
                        ):
                            visited.add((nr, nc))
                            queue.append((nr, nc))
                size = len(cluster)
                for pos in cluster:
                    result[pos] = size

    return result


def xp_for_level(lvl):
    """XP needed per level: 20, 25, 35, 50, 70, ... (+5 more each tier)."""
    base, inc = 20, 5
    return base + inc * (lvl - 1) * lvl // 2
