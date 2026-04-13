#!/usr/bin/env python3
"""Test cave rendering."""

from src.game import Game
import pygame

print("Creating game...")
game = Game()

# Find a cave on the overland map
overland = game.maps["overland"]
cave_col, cave_row = None, None

for r in range(overland.rows):
    for c in range(overland.cols):
        tid = overland.get_tile(r, c)
        if tid in (10, 11):  # CAVE_MOUNTAIN or CAVE_HILL
            cave_col, cave_row = c, r
            print(f"Found cave at ({cave_col}, {cave_row})")
            break
    if cave_col is not None:
        break

if cave_col is None:
    print("No caves found!")
else:
    # Manually transition a player to the cave
    from src.config import TILE

    player = game.player1
    player.x = cave_col * TILE + TILE // 2
    player.y = cave_row * TILE + TILE // 2

    print(f"\nSetting player1 position to cave: ({player.x}, {player.y})")

    # Trigger cave transition
    game.check_cave_transitions(player, overland)

    print(f"Player current_map: {player.current_map}")
    print(f"Maps in game.maps: {list(game.maps.keys())}")

    if player.current_map in game.maps:
        cave_map = game.maps[player.current_map]
        print(f"\nCave map found:")
        print(f"  - Size: {cave_map.cols}x{cave_map.rows}")
        print(f"  - Tileset: {cave_map.tileset}")
        print(f"  - Player new pos: ({player.x}, {player.y})")

        # Check what tiles are around the player
        p_col = int(player.x) // TILE
        p_row = int(player.y) // TILE
        print(f"  - Tile pos: ({p_col}, {p_row})")

        tile_at_player = cave_map.get_tile(p_row, p_col)
        print(f"  - Tile at player: {tile_at_player}")
    else:
        print(f"ERROR: Player's map not in game.maps!")

print("\nTest complete!")
