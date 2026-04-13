"""Tile definitions and properties."""
from src.config import GRASS, DIRT, STONE, IRON_ORE, GOLD_ORE, DIAMOND_ORE, TREE, WATER, HOUSE, MOUNTAIN

TILE_INFO = {
    GRASS:       {"name": "Grass",    "color": (76, 153, 0),    "mineable": False, "hp": 0,  "drop": None,       "drop_color": None},
    DIRT:        {"name": "Dirt",     "color": (139, 90, 43),   "mineable": True,  "hp": 15, "drop": "Dirt",     "drop_color": (139, 90, 43)},
    STONE:       {"name": "Stone",    "color": (136, 140, 141), "mineable": True,  "hp": 30, "drop": "Stone",    "drop_color": (136, 140, 141)},
    IRON_ORE:    {"name": "Iron Ore", "color": (180, 130, 100), "mineable": True,  "hp": 45, "drop": "Iron",     "drop_color": (180, 130, 100)},
    GOLD_ORE:    {"name": "Gold Ore", "color": (230, 200, 50),  "mineable": True,  "hp": 60, "drop": "Gold",     "drop_color": (230, 200, 50)},
    DIAMOND_ORE: {"name": "Diamond",  "color": (100, 220, 255), "mineable": True,  "hp": 80, "drop": "Diamond",  "drop_color": (100, 220, 255)},
    TREE:        {"name": "Tree",     "color": (34, 100, 34),   "mineable": True,  "hp": 20, "drop": "Wood",     "drop_color": (139, 105, 60)},
    WATER:       {"name": "Water",    "color": (28, 100, 180),  "mineable": False, "hp": 0,  "drop": None,       "drop_color": None},
    HOUSE:       {"name": "House",    "color": (160, 82, 45),   "mineable": False, "hp": 0,  "drop": None,       "drop_color": None},
    MOUNTAIN:    {"name": "Mountain", "color": (90, 80, 75),    "mineable": True,  "hp": 50, "drop": "Stone",    "drop_color": (136, 140, 141)},
}

BLOCKING_TILES = (WATER, MOUNTAIN)
