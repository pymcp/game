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
    CAVE_MOUNTAIN,
    CAVE_HILL,
    CAVE_EXIT,
    PIER,
    BOAT,
    TREASURE_CHEST,
    OCEAN_ISLAND_CHANCE,
)
from src.data import ENEMY_TYPES, EnemyEnvironment


def generate_world() -> list[list[int]]:
    """Return a 2-D list of tile-type IDs using simple noise-like placement."""
    # Start entirely as ocean; the island mask determines land vs water
    world = [[WATER for _ in range(WORLD_COLS)] for _ in range(WORLD_ROWS)]

    land_mask = _generate_island_mask(WORLD_ROWS, WORLD_COLS)

    # Stamp grass on all land tiles
    for r in range(WORLD_ROWS):
        for c in range(WORLD_COLS):
            if land_mask[r][c]:
                world[r][c] = GRASS

    def scatter(tile_id, count, cluster_min, cluster_max):
        for _ in range(count):
            cx = random.randint(0, WORLD_COLS - 1)
            cy = random.randint(0, WORLD_ROWS - 1)
            if not land_mask[cy][cx]:
                continue
            size = random.randint(cluster_min, cluster_max)
            for __ in range(size):
                nx = cx + random.randint(-2, 2)
                ny = cy + random.randint(-2, 2)
                if 0 <= nx < WORLD_COLS and 0 <= ny < WORLD_ROWS and land_mask[ny][nx]:
                    world[ny][nx] = tile_id

    scatter(DIRT, 60, 4, 12)
    scatter(STONE, 45, 3, 10)
    scatter(TREE, 70, 2, 6)
    scatter(IRON_ORE, 25, 2, 5)
    scatter(GOLD_ORE, 15, 1, 4)
    scatter(DIAMOND_ORE, 8, 1, 3)

    # Mountains: place with higher clustering to create ranges
    _generate_mountain_ranges(world, land_mask)

    # Generate rivers from mountains with lakes
    _generate_rivers_and_lakes(world)

    # Generate cave entrances
    _place_cave_entrances(world)

    # Place a starting pier + treasure chest for testing
    _place_pier_and_chest(world)

    return world


def generate_ocean_sector(
    sx: int, sy: int, world_seed: int
) -> tuple[list[list[int]], bool]:
    """Generate a deterministic 80×60 ocean sector at grid position (sx, sy).

    The result is fully reproducible: calling with the same arguments always
    returns the same world layout.  Sector (0,0) is the home island and should
    never be generated here — use the existing generate_world() for that.

    Returns a tuple (world, has_island) where world is a 2-D list of tile IDs
    (WORLD_ROWS rows × WORLD_COLS cols) and has_island is True when the sector
    contains a full generated island (not just atolls).
    """
    # Deterministic seed derived from sector coordinates and the world seed
    sector_seed = hash((world_seed, sx, sy)) & 0xFFFF_FFFF
    rng = random.Random(sector_seed)

    has_island = rng.random() < OCEAN_ISLAND_CHANCE

    if has_island:
        # Generate a full island world using the same seeded rng
        _prev_state = random.getstate()
        random.setstate(rng.getstate())
        world = generate_world()
        # Re-sync rng state in case callers chain calls (not strictly needed)
        random.setstate(_prev_state)
        return world, True

    # --- Ocean-only sector: water + rocks + atolls ---
    world = [[WATER for _ in range(WORLD_COLS)] for _ in range(WORLD_ROWS)]

    # Rock shoals: tight clusters of MOUNTAIN tiles (impassable, navigable around)
    num_shoals = rng.randint(2, 6)
    for _ in range(num_shoals):
        cx = rng.randint(5, WORLD_COLS - 6)
        cy = rng.randint(5, WORLD_ROWS - 6)
        cluster_size = rng.randint(3, 10)
        for __ in range(cluster_size):
            nx = cx + rng.randint(-3, 3)
            ny = cy + rng.randint(-3, 3)
            if 0 <= nx < WORLD_COLS and 0 <= ny < WORLD_ROWS:
                world[ny][nx] = MOUNTAIN

    # Tiny atolls: small GRASS patches (scenic, players can land briefly)
    num_atolls = rng.randint(0, 3)
    for _ in range(num_atolls):
        cx = rng.randint(8, WORLD_COLS - 9)
        cy = rng.randint(8, WORLD_ROWS - 9)
        size = rng.randint(1, 5)
        for __ in range(size):
            nx = cx + rng.randint(-2, 2)
            ny = cy + rng.randint(-2, 2)
            if 0 <= nx < WORLD_COLS and 0 <= ny < WORLD_ROWS:
                world[ny][nx] = GRASS

    return world, False


def _generate_island_mask(rows: int, cols: int) -> list[list[bool]]:
    """Generate a boolean mask (True = land) using a warped radial falloff.

    Multiple octaves of sine-wave noise deform the coastline into an organic
    island shape that changes every run.
    """
    cx = cols / 2.0
    cy = rows / 2.0

    # Each octave gets a random phase so no two islands look alike
    num_octaves = 8
    phases = [random.uniform(0, 2 * math.pi) for _ in range(num_octaves)]
    # Low frequencies create big bays/peninsulas; high frequencies add fine detail
    freqs = [1.5, 2.5, 3.7, 5.3, 7.0, 11.0, 15.0, 21.0]
    amps = [0.20, 0.13, 0.09, 0.06, 0.04, 0.03, 0.02, 0.01]

    # How large the island is as a fraction of the half-extents (0=centre, 1=edge)
    island_radius = random.uniform(0.58, 0.72)

    mask = [[False] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            # Normalise to [-1, 1] per axis so the island fits the world aspect ratio
            nx = (c - cx) / (cols / 2.0)
            ny = (r - cy) / (rows / 2.0)

            dist = math.sqrt(nx * nx + ny * ny)
            angle = math.atan2(ny, nx)

            # Noise is scaled by dist so it fades to zero at the centre,
            # guaranteeing land there while still producing a jagged coastline
            noise = dist * sum(
                amp * math.sin(freq * angle + phase)
                for freq, amp, phase in zip(freqs, amps, phases)
            )

            mask[r][c] = dist < island_radius + noise

    return mask


def _generate_mountain_ranges(
    world: list[list[int]], land_mask: list[list[bool]] | None = None
) -> None:
    """Generate mountains in interconnected ranges for better landscape."""
    # First, place initial mountain clusters
    for _ in range(40):  # More initial clusters than before (was 30)
        cx = random.randint(0, WORLD_COLS - 1)
        cy = random.randint(0, WORLD_ROWS - 1)
        if land_mask is not None and not land_mask[cy][cx]:
            continue
        size = random.randint(8, 24)  # Larger clusters (was 6-18)

        # Place initial cluster
        for __ in range(size):
            nx = cx + random.randint(-3, 3)
            ny = cy + random.randint(-3, 3)
            if 0 <= nx < WORLD_COLS and 0 <= ny < WORLD_ROWS:
                if land_mask is None or land_mask[ny][nx]:
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


def _generate_rivers_and_lakes(world: list[list[int]]) -> None:
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


def _trace_river(
    world: list[list[int]], start_col: int, start_row: int, max_length: int = 80
) -> None:
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


def _create_lake(
    world: list[list[int]],
    center_col: int,
    center_row: int,
    radius_range: tuple[int, int] = (1, 2),
) -> None:
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


def spawn_enemies(world: list[list[int]]) -> list:
    """Scatter overland enemies on walkable tiles."""
    from src.entities import Enemy

    overland_types = [
        k
        for k, v in ENEMY_TYPES.items()
        if EnemyEnvironment.OVERLAND in v.get("environments", [])
    ]
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
                    enemy_key = random.choice(overland_types)
                    count = spawn_count.get(enemy_key, 0)
                    if count >= ENEMY_TYPES[enemy_key]["maximum"]:
                        continue
                    spawn_count[enemy_key] = count + 1
                    enemies.append(Enemy(cx, cy, enemy_key))
                    break
    return enemies


def _place_pier_and_chest(world: list[list[int]]) -> None:
    """Place one pier (2 PIER tiles + BOAT tile) and an adjacent TREASURE_CHEST.

    Finds a coastal GRASS tile that has at least 2 consecutive WATER tiles in
    some cardinal direction, then stamps the pier/boat and a chest on a land
    tile perpendicular to the pier.
    """
    rows = len(world)
    cols = len(world[0]) if rows > 0 else 0

    # Collect all candidate positions: (col, row, dc, dr)
    candidates = []
    for r in range(1, rows - 3):
        for c in range(1, cols - 3):
            if world[r][c] not in (GRASS, DIRT):
                continue
            for dc, dr in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                c1, r1 = c + dc, r + dr
                c2, r2 = c + dc * 2, r + dr * 2
                if (
                    0 <= c1 < cols
                    and 0 <= r1 < rows
                    and 0 <= c2 < cols
                    and 0 <= r2 < rows
                    and world[r1][c1] == WATER
                    and world[r2][c2] == WATER
                ):
                    candidates.append((c, r, dc, dr))

    if not candidates:
        return

    pc, pr, dc, dr = random.choice(candidates)

    # Stamp pier and boat
    world[pr + dr][pc + dc] = PIER
    world[pr + dr * 2][pc + dc * 2] = PIER
    c3, r3 = pc + dc * 3, pr + dr * 3
    if 0 <= c3 < cols and 0 <= r3 < rows and world[r3][c3] == WATER:
        world[r3][c3] = BOAT

    # Place chest on an adjacent land tile perpendicular to pier direction
    perp_dirs = [(-dr, dc), (dr, -dc)]
    placed_chest = False
    for pdc, pdr in perp_dirs:
        cc, rr = pc + pdc, pr + pdr
        if 0 <= cc < cols and 0 <= rr < rows and world[rr][cc] in (GRASS, DIRT):
            world[rr][cc] = TREASURE_CHEST
            placed_chest = True
            break

    if not placed_chest:
        # Fallback: place behind the pier start point
        bc, br = pc - dc, pr - dr
        if 0 <= bc < cols and 0 <= br < rows and world[br][bc] in (GRASS, DIRT):
            world[br][bc] = TREASURE_CHEST


def _is_adjacent_to_mountain(world: list[list[int]], col: int, row: int) -> bool:
    """Check if a tile is adjacent to a mountain."""
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            adj_col, adj_row = col + dc, row + dr
            if 0 <= adj_col < WORLD_COLS and 0 <= adj_row < WORLD_ROWS:
                if world[adj_row][adj_col] == MOUNTAIN:
                    return True
    return False


def _place_cave_entrances(world: list[list[int]]) -> None:
    """Place cave entrances on the world map."""
    # Place caves near and around mountains, and in some hill areas
    cave_count = 0
    max_caves = 15

    for _ in range(100):  # Try up to 100 times
        if cave_count >= max_caves:
            break

        col = random.randint(1, WORLD_COLS - 2)
        row = random.randint(1, WORLD_ROWS - 2)

        # Only place caves on grass or dirt
        if world[row][col] not in (GRASS, DIRT):
            continue

        # Check if this location could be a good cave entrance
        is_adj_mountain = _is_adjacent_to_mountain(world, col, row)

        # Either place near mountains or in isolated hill areas
        if is_adj_mountain or (random.random() < 0.3 and world[row][col] == GRASS):
            # Decide which cave type based on mountain proximity
            cave_type = CAVE_MOUNTAIN if is_adj_mountain else CAVE_HILL
            world[row][col] = cave_type
            cave_count += 1
