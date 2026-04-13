#!/usr/bin/env python3
"""Debug cave system."""

from src.world.generation import generate_world, generate_cave_map
from src.config import CAVE_MOUNTAIN, CAVE_HILL, WORLD_COLS, WORLD_ROWS, TILE

# Generate world
print("Generating world...")
world = generate_world()

# Check if any caves were placed
cave_count = 0
cave_positions = []
for r in range(WORLD_ROWS):
    for c in range(WORLD_COLS):
        if world[r][c] in (CAVE_MOUNTAIN, CAVE_HILL):
            cave_count += 1
            cave_positions.append((c, r, world[r][c]))

print(f"Found {cave_count} caves on overland map")
if cave_positions:
    for col, row, tile_type in cave_positions[:5]:
        tile_name = "CAVE_MOUNTAIN" if tile_type == CAVE_MOUNTAIN else "CAVE_HILL"
        print(f"  - Cave at ({col}, {row}): {tile_name}")

    # Try generating one of the caves
    print(f"\nGenerating first cave at {cave_positions[0][:2]}...")
    cave = generate_cave_map(cave_positions[0][0], cave_positions[0][1])
    print(f"Cave map created: {cave.cols}x{cave.rows}")
    print(f"Exit at: ({cave.exit_col}, {cave.exit_row})")
    print(f"Entrance at: ({cave.entrance_col}, {cave.entrance_row})")
    
    # Check what tiles are in the cave
    from src.config import GRASS, STONE, IRON_ORE, GOLD_ORE, DIAMOND_ORE
    tile_counts = {}
    for r in range(cave.rows):
        for c in range(cave.cols):
            tid = cave.get_tile(r, c)
            tile_counts[tid] = tile_counts.get(tid, 0) + 1
    
    tile_names = {
        GRASS: "GRASS",
        STONE: "STONE", 
        IRON_ORE: "IRON_ORE",
        GOLD_ORE: "GOLD_ORE",
        DIAMOND_ORE: "DIAMOND_ORE",
    }
    
    print("\nCave tile composition:")
    for tid, count in sorted(tile_counts.items()):
        name = tile_names.get(tid, f"TILE_{tid}")
        print(f"  - {name}: {count} tiles")
else:
    print("ERROR: No caves generated on world!")
