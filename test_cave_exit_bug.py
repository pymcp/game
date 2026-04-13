#!/usr/bin/env python3
"""Test that cave entry doesn't immediately trigger exit."""

from src.game import Game
from src.config import TILE, CAVE_EXIT

print("Creating game...")
game = Game()

# Find a cave
overland = game.maps["overland"]
cave_col, cave_row = None, None
for r in range(overland.rows):
    for c in range(overland.cols):
        if overland.get_tile(r, c) in (10, 11):
            cave_col, cave_row = c, r
            break
    if cave_col:
        break

print(f"Cave at ({cave_col}, {cave_row})")

# Move player to cave entrance
player = game.player1
player.x = cave_col * TILE + TILE // 2
player.y = cave_row * TILE + TILE // 2

# --- Simulate what update() does ---

# Step 1: Get map
map1 = game.get_player_current_map(player)
print(f"\n1. Before transition: current_map={player.current_map}")

# Step 2: Check cave transitions
game.check_cave_transitions(player, map1)
print(
    f"2. After cave entry: current_map={player.current_map}, pos=({player.x}, {player.y})"
)

# Step 3: Refresh map (like update() does)
map1 = game.get_player_current_map(player)

# Step 4: Check cave exits (THE BUG - this used to immediately eject the player)
game.check_cave_exits(player, map1)
print(
    f"3. After exit check: current_map={player.current_map}, pos=({player.x}, {player.y})"
)

if player.current_map == "overland":
    print("\n*** BUG STILL PRESENT: Player was ejected back to overland! ***")
else:
    print(f"\n*** FIX WORKS: Player remains in cave {player.current_map} ***")

    # Verify the tile at spawn is not CAVE_EXIT
    tile_col = int(player.x) // TILE
    tile_row = int(player.y) // TILE
    tile_at_spawn = map1.get_tile(tile_row, tile_col)
    print(
        f"   Spawn tile ({tile_col}, {tile_row}): type={tile_at_spawn} (CAVE_EXIT={CAVE_EXIT})"
    )

    # Verify the exit tile exists somewhere
    found_exit = False
    for r in range(map1.rows):
        for c in range(map1.cols):
            if map1.get_tile(r, c) == CAVE_EXIT:
                print(f"   Exit tile at ({c}, {r})")
                found_exit = True
    if not found_exit:
        print("   WARNING: No CAVE_EXIT tile found in cave!")
