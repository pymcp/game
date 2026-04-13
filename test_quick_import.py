#!/usr/bin/env python3
"""Quick test script to check if modules import."""

import sys
print("Python version:", sys.version)

print("\n=== Testing imports ===")

try:
    print("Importing pygame...", end=" ")
    import pygame
    print("OK")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

try:
    print("Importing src.config...", end=" ")
    from src.config import GRASS, CAVE_MOUNTAIN, CAVE_HILL
    print("OK")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

try:
    print("Importing src.world.map...", end=" ")
    from src.world.map import GameMap
    print("OK")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

try:
    print("Importing src.world.generation...", end=" ")
    from src.world.generation import generate_cave_map, generate_world
    print("OK")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

try:
    print("Importing src.game...", end=" ")
    from src.game import Game
    print("OK")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

print("\n=== All imports successful! ===")
