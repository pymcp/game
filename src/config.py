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

# Minimum solid-wall border for enclosed maps (cave, underwater, portal realm).
# Ensures the first walkable tile is always beyond the HUD panels:
#   Left/Top HUD panel: ~248px wide, ~293px tall  → 10 tiles (10×32=320) clears both.
#   Right minimap:       114px                    → 4 tiles minimum; 10 keeps symmetry.
#   Bottom HUD:          138px                    → 5 tiles minimum; 10 keeps symmetry.
MAP_BORDER = 10

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
PIER = 14  # Dock tile extending into ocean (walkable)
BOAT = 15  # Boat tile moored next to pier (board by walking on)
TREASURE_CHEST = 16  # Chest tile on land containing loot
SAND = 17  # Underwater sand floor tile (walkable)
CORAL = 18  # Mineable coral formation (drops "Coral")
REEF = 19  # Solid reef wall (impassable, non-mineable)
DIVE_EXIT = 20  # Exit tile in underwater map (returns player to surface)
PORTAL_RUINS = 21  # Crumbling ancient portal (unrestored)
PORTAL_ACTIVE = 22  # Restored ancient portal (enterable)
ANCIENT_STONE = 23  # Ritual altar stone used in portal quests
PORTAL_WALL = 24  # Impassable ancient stone wall (portal realm)
PORTAL_FLOOR = 25  # Walkable ancient stone floor (portal realm)

# Housing environment tiles
WOOD_FLOOR = 26       # Walkable plank floor inside a house
WOOD_WALL = 27        # Solid wood wall (impassable, non-mineable)
WORKTABLE = 28        # Crafting bench inside a house environment
HOUSE_EXIT = 29       # Exit tile inside a housing environment (returns to overland)
DIRT_PATH = 30        # Walkable dirt path (settlement interiors, Hamlet)
COBBLESTONE = 31      # Walkable cobblestone path (settlement interiors, Town/Large Town)
SETTLEMENT_HOUSE = 32 # Enterable sub-house tile within a settlement environment
STONE_PATH = 33       # Walkable flat-stone path (settlement interiors, Village)
ROAD = 34             # Walkable paved road (settlement interiors, City)

# Settlement tiers: minimum connected-house cluster size to reach each tier
SETTLEMENT_TIER_SIZES = [1, 2, 4, 9, 16, 25]
SETTLEMENT_TIER_NAMES = ["Cottage", "Hamlet", "Village", "Town", "Large Town", "City"]

HOUSE_BUILD_COST = 20  # Dirt required to build a house
PIER_BUILD_COST = 5  # Wood required to build a pier
BOAT_BUILD_COST = 1  # Wood required to build a boat (+ 1 Sail)
SCUBA_BUILD_COST = 5  # Wood required to craft Scuba Gear at a house
SECTOR_WIPE_DURATION = 30   # frames for the edge-crossing scroll wipe (~0.5 s at 60 fps)
PORTAL_WARP_DURATION = 180  # frames for the portal vortex warp effect (~3 s at 60 fps)
OCEAN_ISLAND_CHANCE = 0.25  # Probability any non-home sector contains an island
