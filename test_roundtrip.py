#!/usr/bin/env python3
"""Test full cave enter + exit round-trip."""
from src.game import Game
from src.config import TILE, CAVE_EXIT, CAVE_MOUNTAIN, CAVE_HILL

game = Game()
overland = game.maps["overland"]

# Find a cave
for r in range(overland.rows):
    for c in range(overland.cols):
        if overland.get_tile(r, c) in (CAVE_MOUNTAIN, CAVE_HILL):
            cave_col, cave_row = c, r
            break
    else:
        continue
    break

player = game.player1

# --- ENTER CAVE ---
player.x = cave_col * TILE + TILE // 2
player.y = cave_row * TILE + TILE // 2
m = game.get_player_current_map(player)
game.check_cave_transitions(player, m)
print(f"After ENTER: map={player.current_map}, pos=({int(player.x)}, {int(player.y)})")

# Verify still in cave after exit check on same frame
m = game.get_player_current_map(player)
game.check_cave_exits(player, m)
print(f"After exit check (same frame): map={player.current_map}")
assert player.current_map != "overland", "BUG: ejected on entry frame"

# --- WALK TO EXIT ---
cave_map = game.get_player_current_map(player)
player.x = cave_map.exit_col * TILE + TILE // 2
player.y = cave_map.exit_row * TILE + TILE // 2
m = game.get_player_current_map(player)
game.check_cave_exits(player, m)
print(f"After EXIT: map={player.current_map}, pos=({int(player.x)}, {int(player.y)})")
assert player.current_map == "overland", "BUG: didn't exit cave"

# Verify NOT re-entering cave on same frame
tile_col = int(player.x) // TILE
tile_row = int(player.y) // TILE
tile_here = overland.get_tile(tile_row, tile_col)
print(f"Landing tile ({tile_col},{tile_row}): type={tile_here}")
assert tile_here not in (CAVE_MOUNTAIN, CAVE_HILL), "BUG: landed on cave tile"

m = game.get_player_current_map(player)
game.check_cave_transitions(player, m)
print(f"After transition check (same frame): map={player.current_map}")
assert player.current_map == "overland", "BUG: re-entered cave on exit frame"

print("\nAll checks passed!")
