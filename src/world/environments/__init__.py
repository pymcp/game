"""Environment module — world generation strategies for different biomes."""

from src.world.environments.overland import OverlandEnvironment
from src.world.environments.cave import CaveEnvironment

__all__ = ["OverlandEnvironment", "CaveEnvironment"]
