#!/usr/bin/env python
"""Test script to check imports."""

try:
    from src.world.map import GameMap
    print("✓ GameMap imported")
except Exception as e:
    print(f"✗ GameMap import failed: {e}")

try:
    from src.world.generation import generate_cave_map
    print("✓ generate_cave_map imported")
except Exception as e:
    print(f"✗ generate_cave_map import failed: {e}")

try:
    from src.config import CAVE_MOUNTAIN, CAVE_HILL
    print("✓ Cave constants imported")
except Exception as e:
    print(f"✗ Cave constants import failed: {e}")

print("\nAll imports checked!")
