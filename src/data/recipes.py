"""Crafting recipes available at a worktable inside a housing environment.

Each recipe has:
  - "name": str
  - "cost": {item: qty}
  - "result": {"item": str, "qty": int}
  - "min_tier": int — minimum housing tier (0-5) required to craft this recipe
"""

# Material craft cost per armor piece
_ARMOR_COSTS: dict[str, dict[str, int]] = {
    "Stone": {"Stone": 5},
    "Iron": {"Iron": 3},
    "Gold": {"Gold": 3},
    "Diamond": {"Diamond": 2},
    "Coral": {"Coral": 4},
    "Ancient Stone": {"Ancient Stone": 2},
}

# Minimum housing tier required per armor material (0 = Cottage, 5 = City)
_ARMOR_MIN_TIER: dict[str, int] = {
    "Stone": 0,
    "Iron": 0,
    "Gold": 1,
    "Diamond": 2,
    "Coral": 3,
    "Ancient Stone": 4,
}

_SLOTS = ["Helmet", "Chest", "Legs", "Boots"]


def _armor_recipes() -> list[dict]:
    recipes = []
    for mat, cost in _ARMOR_COSTS.items():
        for slot in _SLOTS:
            name = f"{mat} {slot}"
            recipes.append(
                {
                    "name": name,
                    "cost": cost,
                    "result": {"item": name, "qty": 1},
                    "min_tier": _ARMOR_MIN_TIER[mat],
                }
            )
    return recipes


RECIPES: list[dict] = [
    {
        "name": "Scuba Gear",
        "cost": {"Wood": 5},
        "result": {"item": "Scuba Gear", "qty": 1},
        "min_tier": 0,
    },
    # Armor pieces (24 recipes — 6 materials × 4 slots)
    *_armor_recipes(),
    # Accessories (5 recipes)
    {
        "name": "Iron Ring",
        "cost": {"Iron": 5},
        "result": {"item": "Iron Ring", "qty": 1},
        "min_tier": 1,
    },
    {
        "name": "Gold Ring",
        "cost": {"Gold": 5},
        "result": {"item": "Gold Ring", "qty": 1},
        "min_tier": 2,
    },
    {
        "name": "Diamond Ring",
        "cost": {"Diamond": 3},
        "result": {"item": "Diamond Ring", "qty": 1},
        "min_tier": 2,
    },
    {
        "name": "Coral Amulet",
        "cost": {"Coral": 6},
        "result": {"item": "Coral Amulet", "qty": 1},
        "min_tier": 3,
    },
    {
        "name": "Ancient Amulet",
        "cost": {"Ancient Stone": 4},
        "result": {"item": "Ancient Amulet", "qty": 1},
        "min_tier": 4,
    },
]
