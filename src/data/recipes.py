"""Crafting recipes available at a house workbench."""

# Each recipe: {"name": str, "cost": {item: qty}, "result": {"item": str, "qty": int}}
RECIPES: list[dict] = [
    {
        "name": "Scuba Gear",
        "cost": {"Wood": 5},
        "result": {"item": "Scuba Gear", "qty": 1},
    },
]
