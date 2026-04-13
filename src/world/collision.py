"""Collision detection and world queries."""

from src.config import TILE, WORLD_COLS, WORLD_ROWS
from src.data import BLOCKING_TILES


def tile_at(world, wx, wy):
    """Get tile ID at world position, or -1 if out of bounds."""
    col = int(wx) // TILE
    row = int(wy) // TILE
    if col < 0 or col >= WORLD_COLS or row < 0 or row >= WORLD_ROWS:
        return -1
    return world[row][col]


def pos_in_bounds(wx, wy):
    """Check if world position is within world bounds."""
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


def out_of_bounds(cx, cy, half):
    """Check if a circle would leave the world bounds."""
    for ox in (-half, half):
        for oy in (-half, half):
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


def xp_for_level(lvl):
    """XP needed per level: 20, 25, 35, 50, 70, ... (+5 more each tier)."""
    base, inc = 20, 5
    return base + inc * (lvl - 1) * lvl // 2
