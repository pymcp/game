#!/usr/bin/env python3
"""Comprehensive cave system test."""

import sys
from src.game import Game
from src.config import TILE, WORLD_COLS, WORLD_ROWS

print("=" * 60)
print("CAVE SYSTEM COMPREHENSIVE TEST")
print("=" * 60)

print("\n1. Creating game...")
game = Game()
print(f"   Maps in system: {list(game.maps.keys())}")
print(f"   Player1 map: {game.player1.current_map}")
print(f"   Player2 map: {game.player2.current_map}")

# Find a cave on the overland map
print("\n2. Scanning for caves on overland map...")
overland = game.maps["overland"]
cave_positions = []
for r in range(overland.rows):
    for c in range(overland.cols):
        tid = overland.get_tile(r, c)
        if tid in (10, 11):  # CAVE_MOUNTAIN or CAVE_HILL
            cave_positions.append((c, r, tid))

print(f"   Found {len(cave_positions)} caves")
if cave_positions:
    cave_col, cave_row, tile_type = cave_positions[0]
    print(f"   Using cave at ({cave_col}, {cave_row}), type={tile_type}")
else:
    print("   ERROR: No caves found!")
    sys.exit(1)

# Manually place player on cave entrance
print(f"\n3. Moving player1 to cave entrance...")
player1 = game.player1
old_pos = (player1.x, player1.y)
player1.x = cave_col * TILE + TILE // 2
player1.y = cave_row * TILE + TILE // 2
print(f"   Old position: {old_pos}")
print(f"   New position: ({player1.x}, {player1.y})")
print(f"   Player current_map: {player1.current_map}")
print(f"   get_player_current_map returns: {game.get_player_current_map(player1)}")

# Get the map before transition
overland_map = game.get_player_current_map(player1)
print(f"   Current map size: {overland_map.cols}x{overland_map.rows}")

# Trigger cave transition manually
print(f"\n4. Triggering check_cave_transitions...")
game.check_cave_transitions(player1, overland_map)

print(f"\n5. After transition:")
print(f"   Player1 position: ({player1.x}, {player1.y})")
print(f"   Player1 current_map: {player1.current_map}")
print(f"   Camera1: ({game.cam1_x}, {game.cam1_y})")

# Check if cave map was created
cave_key = (cave_col, cave_row)
print(f"\n6. Checking cave map storage...")
print(f"   Maps dict: {list(game.maps.keys())}")
if cave_key in game.maps:
    cave_map = game.maps[cave_key]
    print(f"   ✓ Cave map exists!")
    print(f"   Cave map size: {cave_map.cols}x{cave_map.rows}")
    print(f"   Cave map tileset: {cave_map.tileset}")
else:
    print(f"   ✗ CAVE MAP NOT FOUND for key {cave_key}")

# Check what get_player_current_map returns now
print(f"\n7. Checking get_player_current_map after transition...")
current_map_for_player = game.get_player_current_map(player1)
if current_map_for_player:
    print(f"   Map found: {current_map_for_player.cols}x{current_map_for_player.rows}")
    print(f"   Tileset: {current_map_for_player.tileset}")
    print(
        f"   Exit marker: ({current_map_for_player.exit_col}, {current_map_for_player.exit_row})"
    )
else:
    print(f"   ✗ get_player_current_map returned None!")

# Simulate what the draw function would do
print(f"\n8. Simulating draw function...")
current_map = game.get_player_current_map(player1)
if current_map is None:
    print("   WARNING: map is None, falling back to overland")
    current_map = game.maps["overland"]

cam_x = game.cam1_x
cam_y = game.cam1_y
view_w = game.viewport_w
view_h = game.viewport_h

world_cols = current_map.cols
world_rows = current_map.rows
print(f"   Using map: {world_cols}x{world_rows}")
print(f"   Camera: ({cam_x}, {cam_y})")
print(f"   Viewport: {view_w}x{view_h}")

start_col = max(0, int(cam_x) // TILE)
end_col = min(world_cols, int(cam_x + view_w) // TILE + 2)
start_row = max(0, int(cam_y) // TILE)
end_row = min(world_rows, int(cam_y + view_h) // TILE + 2)

print(f"   Render range: cols=[{start_col}, {end_col}], rows=[{start_row}, {end_row}]")
if start_col < end_col and start_row < end_row:
    tile_count = (end_col - start_col) * (end_row - start_row)
    print(f"   ✓ Will render {tile_count} tiles")
else:
    print(f"   ✗ EMPTY RENDER RANGE!")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
