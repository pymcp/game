"""Game configuration and constants."""

# Display
SCREEN_W, SCREEN_H = 1920, 1080
TILE = 32
FPS = 60

# Split-screen for 2 players (each gets half the width)
VIEWPORT_W = SCREEN_W // 2
VIEWPORT_H = SCREEN_H

# World size in tiles
WORLD_COLS = 80
WORLD_ROWS = 60

# Colors
BG = (30, 30, 46)
UI_BG = (20, 20, 30, 200)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Tile types
GRASS = 0
DIRT = 1
STONE = 2
IRON_ORE = 3
GOLD_ORE = 4
DIAMOND_ORE = 5
TREE = 6
WATER = 7
HOUSE = 8
MOUNTAIN = 9
CAVE_MOUNTAIN = 10  # Cave entrance that looks like mountain (adjacent to mountain)
CAVE_HILL = 11  # Cave entrance that looks like hill (not adjacent to mountain)
CAVE_EXIT = 12  # Exit tile inside a cave (returns player to overland)
CAVE_WALL = 13  # Solid cave wall tile (impassable, non-mineable)

# Settlement tiers: minimum connected-house cluster size to reach each tier
SETTLEMENT_TIER_SIZES = [1, 2, 4, 9, 16, 25]
SETTLEMENT_TIER_NAMES = ["Cottage", "Hamlet", "Village", "Town", "Large Town", "City"]
