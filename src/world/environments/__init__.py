"""Environment module — world generation strategies for different biomes."""

from src.world.environments.overland import OverlandEnvironment
from src.world.environments.cave import CaveEnvironment
from src.world.environments.underwater import UnderwaterEnvironment

__all__ = ["OverlandEnvironment", "CaveEnvironment", "UnderwaterEnvironment"]
