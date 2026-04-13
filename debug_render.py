#!/usr/bin/env python3
"""Debug cave rendering."""

from src.game import Game
from src.config import TILE
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
    player = game.player1
    player.x = cave_col * TILE + TILE // 2
    player.y = cave_row * TILE + TILE // 2

    print(f"Player position set to: ({player.x}, {player.y})")
    print(f"Player current_map before transition: {player.current_map}")

    # Trigger cave transition
    game.check_cave_transitions(player, overland)

    print(f"\nAfter check_cave_transitions:")
    print(f"  Player current_map: {player.current_map}")
    print(f"  Player position: ({player.x}, {player.y})")
    print(f"  cam1_x: {game.cam1_x}, cam1_y: {game.cam1_y}")
    print(f"  Maps in game.maps: {list(game.maps.keys())}")

    # Check what get_player_current_map returns
    current_map_for_player = game.get_player_current_map(player)
    print(f"\nget_player_current_map returns: {current_map_for_player}")
    if current_map_for_player:
        print(
            f"  Map size: {current_map_for_player.cols}x{current_map_for_player.rows}"
        )
        print(f"  Tileset: {current_map_for_player.tileset}")

    # Now simulate what happens in the draw function
    print(f"\nSimulating draw function:")
    cam_x = game.cam1_x
    cam_y = game.cam1_y
    view_w = game.viewport_w
    view_h = game.viewport_h

    print(f"  Camera: ({cam_x}, {cam_y})")
    print(f"  Viewport: {view_w}x{view_h}")

    start_col = max(0, int(cam_x) // TILE)
    end_col = min(current_map_for_player.cols, int(cam_x + view_w) // TILE + 2)
    start_row = max(0, int(cam_y) // TILE)
    end_row = min(current_map_for_player.rows, int(cam_y + view_h) // TILE + 2)

    print(
        f"  Render range: cols=[{start_col}, {end_col}], rows=[{start_row}, {end_row}]"
    )

    if start_col >= end_col or start_row >= end_row:
        print("  ERROR: Empty render range!")
    else:
        print(f"  Tiles to render: {(end_col - start_col) * (end_row - start_row)}")

        # Check what tiles would be drawn
        tile_at_player_col = int(player.x) // TILE
        tile_at_player_row = int(player.y) // TILE
        print(f"  Player tile pos: ({tile_at_player_col}, {tile_at_player_row})")

        if (
            start_col <= tile_at_player_col < end_col
            and start_row <= tile_at_player_row < end_row
        ):
            tile_at_player = current_map_for_player.get_tile(
                tile_at_player_row, tile_at_player_col
            )
            print(f"  Tile at player: {tile_at_player}")

print("\nTest complete!")
