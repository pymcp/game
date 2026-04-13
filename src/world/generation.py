"""World generation and enemy spawning."""

import random
import math
from src.config import (
    WORLD_COLS,
    WORLD_ROWS,
    TILE,
    GRASS,
    DIRT,
    STONE,
    WATER,
    TREE,
    IRON_ORE,
    GOLD_ORE,
    DIAMOND_ORE,
    MOUNTAIN,
)
from src.data import ENEMY_TYPES


def generate_world():
    """Return a 2-D list of tile-type IDs using simple noise-like placement."""
    world = [[GRASS for _ in range(WORLD_COLS)] for _ in range(WORLD_ROWS)]

    def scatter(tile_id, count, cluster_min, cluster_max):
        for _ in range(count):
            cx = random.randint(0, WORLD_COLS - 1)
            cy = random.randint(0, WORLD_ROWS - 1)
            size = random.randint(cluster_min, cluster_max)
            for __ in range(size):
                nx = cx + random.randint(-2, 2)
                ny = cy + random.randint(-2, 2)
                if 0 <= nx < WORLD_COLS and 0 <= ny < WORLD_ROWS:
                    world[ny][nx] = tile_id

    scatter(DIRT, 60, 4, 12)
    scatter(STONE, 45, 3, 10)
    scatter(TREE, 70, 2, 6)
    scatter(IRON_ORE, 25, 2, 5)
    scatter(GOLD_ORE, 15, 1, 4)
    scatter(DIAMOND_ORE, 8, 1, 3)

    # Mountains: place with higher clustering to create ranges
    _generate_mountain_ranges(world)

    # Generate rivers from mountains with lakes
    _generate_rivers_and_lakes(world)

    return world


def _generate_mountain_ranges(world):
    """Generate mountains in interconnected ranges for better landscape."""
    # First, place initial mountain clusters
    for _ in range(40):  # More initial clusters than before (was 30)
        cx = random.randint(0, WORLD_COLS - 1)
        cy = random.randint(0, WORLD_ROWS - 1)
        size = random.randint(8, 24)  # Larger clusters (was 6-18)

        # Place initial cluster
        for __ in range(size):
            nx = cx + random.randint(-3, 3)
            ny = cy + random.randint(-3, 3)
            if 0 <= nx < WORLD_COLS and 0 <= ny < WORLD_ROWS:
                world[ny][nx] = MOUNTAIN

    # Second pass: expand and connect mountains (create ranges)
    # For each existing mountain, have a chance to place adjacent mountains
    for row in range(WORLD_ROWS):
        for col in range(WORLD_COLS):
            if world[row][col] == MOUNTAIN:
                # 40% chance to spread mountain to adjacent tiles
                if random.random() < 0.40:
                    # Pick a random adjacent tile
                    adj_col = col + random.randint(-1, 1)
                    adj_row = row + random.randint(-1, 1)

                    if 0 <= adj_col < WORLD_COLS and 0 <= adj_row < WORLD_ROWS:
                        # 70% chance to place mountain if adjacent is grass/dirt (not overwrite water)
                        if world[adj_row][adj_col] in (GRASS, DIRT, STONE):
                            world[adj_row][adj_col] = MOUNTAIN


def _generate_rivers_and_lakes(world):
    """Generate rivers flowing from mountain ranges with random lakes."""
    # Find all mountain peaks (isolated mountains or edges of ranges)
    mountain_peaks = []
    for row in range(WORLD_ROWS):
        for col in range(WORLD_COLS):
            if world[row][col] == MOUNTAIN:
                # Check if this is a good starting point (peak-like)
                mountain_peaks.append((col, row))

    # Create rivers from random mountain locations
    num_rivers = max(1, len(mountain_peaks) // 50)
    for _ in range(num_rivers):
        if not mountain_peaks:
            break
        start_col, start_row = random.choice(mountain_peaks)
        _trace_river(world, start_col, start_row)


def _trace_river(world, start_col, start_row, max_length=80):
    """Trace a river from a starting point, creating lakes along the way."""
    col, row = start_col, start_row
    length = 0
    last_lake_distance = 0

    while length < max_length:
        # Don't place water on mountains
        if world[row][col] != MOUNTAIN:
            world[row][col] = WATER

        # Chance to create a lake every 25-50 tiles
        if length - last_lake_distance >= random.randint(25, 50):
            if random.random() < 0.25:  # 25% chance to make a lake at this point
                _create_lake(world, col, row)
                last_lake_distance = length

        # Move river in a somewhat random direction (prefer flowing away from mountains)
        # Create a bias toward edges (as if water flows downhill naturally)
        directions = []

        # Prefer edges by giving them higher weight
        if col < WORLD_COLS // 3:
            directions.extend([(1, 0)] * 3)  # East bias
        elif col > 2 * WORLD_COLS // 3:
            directions.extend([(-1, 0)] * 3)  # West bias
        else:
            directions.extend([(1, 0), (-1, 0)])

        if row < WORLD_ROWS // 3:
            directions.extend([(0, 1)] * 3)  # South bias
        elif row > 2 * WORLD_ROWS // 3:
            directions.extend([(0, -1)] * 3)  # North bias
        else:
            directions.extend([(0, 1), (0, -1)])

        # Add random directions
        directions.extend(
            [(random.randint(-1, 1), random.randint(-1, 1)) for _ in range(4)]
        )

        # Pick a random direction and move
        dx, dy = random.choice(directions)
        new_col = col + dx
        new_row = row + dy

        # Keep river in bounds
        if not (0 <= new_col < WORLD_COLS and 0 <= new_row < WORLD_ROWS):
            break

        col, row = new_col, new_row
        length += 1


def _create_lake(world, center_col, center_row, radius_range=(1, 2)):
    """Create a lake (contiguous water area) around a center point."""
    radius = random.randint(*radius_range)

    # Use a simple flood-fill-like expansion to create a contiguous water area
    lake_tiles = [(center_col, center_row)]
    visited = {(center_col, center_row)}

    while lake_tiles and len(visited) < radius * radius * 2:
        col, row = lake_tiles.pop(0)

        # Place water at this location (unless it's a mountain)
        if world[row][col] != MOUNTAIN:
            world[row][col] = WATER

        # Expand to adjacent tiles randomly
        for dx, dy in [
            (0, 1),
            (1, 0),
            (0, -1),
            (-1, 0),
            (1, 1),
            (-1, -1),
            (1, -1),
            (-1, 1),
        ]:
            new_col, new_row = col + dx, row + dy

            if (
                0 <= new_col < WORLD_COLS
                and 0 <= new_row < WORLD_ROWS
                and (new_col, new_row) not in visited
            ):

                visited.add((new_col, new_row))

                # Higher chance for orthogonal neighbors
                expansion_chance = 0.7 if dx * dy == 0 else 0.4

                if random.random() < expansion_chance:
                    lake_tiles.append((new_col, new_row))


def spawn_enemies(world):
    """Scatter enemies on walkable tiles throughout the world."""
    from src.entities import Enemy

    enemies = []
    spawn_count = {}
    for _ in range(25):
        for attempt in range(20):
            col = random.randint(2, WORLD_COLS - 3)
            row = random.randint(2, WORLD_ROWS - 3)
            if world[row][col] == GRASS:
                cx = col * TILE + TILE // 2
                cy = row * TILE + TILE // 2
                mid_x = (WORLD_COLS // 2) * TILE
                mid_y = (WORLD_ROWS // 2) * TILE
                if math.hypot(cx - mid_x, cy - mid_y) > TILE * 8:
                    enemy_key = random.choice(list(ENEMY_TYPES.keys()))
                    count = spawn_count.get(enemy_key, 0)
                    if count >= ENEMY_TYPES[enemy_key]["maximum"]:
                        continue
                    spawn_count[enemy_key] = count + 1
                    enemies.append(Enemy(cx, cy, enemy_key))
                    break
    return enemies
