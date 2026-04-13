"""Shared pytest fixtures for game manager unit tests."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import Any

import pytest

# Ensure the project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame

from src.config import GRASS, TILE, WORLD_COLS, WORLD_ROWS
from src.world.map import GameMap
from src.world.scene import MapScene
from src.entities.player import Player, CONTROL_SCHEME_PLAYER1, CONTROL_SCHEME_PLAYER2


# ---------------------------------------------------------------------------
# Pygame initialisation (once per session, headless)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _init_pygame() -> None:
    """Initialise pygame with a minimal display so Surface ops work."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((1, 1))


# ---------------------------------------------------------------------------
# Lightweight helpers
# ---------------------------------------------------------------------------


def _make_world(rows: int = 20, cols: int = 20, fill: int = GRASS) -> list[list[int]]:
    """Return a *rows*×*cols* 2-D tile grid filled with *fill*."""
    return [[fill] * cols for _ in range(rows)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_world() -> list[list[int]]:
    """20×20 grass world."""
    return _make_world()


@pytest.fixture()
def mock_game_map(mock_world: list[list[int]]) -> GameMap:
    """A small GameMap backed by *mock_world*."""
    return GameMap(mock_world, tileset="overland")


@pytest.fixture()
def mock_scene(mock_game_map: GameMap) -> MapScene:
    """A MapScene wrapping *mock_game_map*."""
    return MapScene(mock_game_map)


@pytest.fixture()
def player1() -> Player:
    """Player 1 at centre of a 20×20 map."""
    return Player(
        10 * TILE + TILE // 2,
        10 * TILE + TILE // 2,
        player_id=1,
        control_scheme=CONTROL_SCHEME_PLAYER1,
    )


@pytest.fixture()
def player2() -> Player:
    """Player 2 near Player 1."""
    return Player(
        11 * TILE + TILE // 2,
        10 * TILE + TILE // 2,
        player_id=2,
        control_scheme=CONTROL_SCHEME_PLAYER2,
    )


class MockGame:
    """Lightweight stand-in for the real Game class.

    Provides just enough surface area for managers to work:
    maps, players, screen, fonts, and effect routing.
    """

    def __init__(
        self,
        scene: MapScene,
        player1: Player,
        player2: Player,
    ) -> None:
        self.maps: dict[str | tuple, MapScene] = {"overland": scene}
        self.maps[("sector", 0, 0)] = scene
        self.player1 = player1
        self.player2 = player2
        player1.current_map = "overland"
        player2.current_map = "overland"

        # Pygame surfaces / fonts
        self.screen = pygame.display.get_surface() or pygame.Surface((640, 360))
        self.font = pygame.font.Font(None, 16)
        self.font_ui_sm = pygame.font.Font(None, 22)
        self.font_ui_xs = pygame.font.Font(None, 16)
        self.font_dc_big = pygame.font.Font(None, 38)
        self.font_dc_med = pygame.font.Font(None, 26)
        self.font_dc_sm = pygame.font.Font(None, 18)

        self.viewport_w: int = 320
        self.viewport_h: int = 360

        # Camera positions
        self.cam1_x: float = 0.0
        self.cam1_y: float = 0.0
        self.cam2_x: float = 0.0
        self.cam2_y: float = 0.0

        # Effect collectors (simple lists for testing)
        self._floats: list[Any] = []
        self._particles: list[Any] = []
        self.floats = SimpleNamespace(
            append=lambda item: self._floats.append(item),
            extend=lambda items: self._floats.extend(items),
        )
        self.particles = SimpleNamespace(
            append=lambda item: self._particles.append(item),
            extend=lambda items: self._particles.extend(items),
        )

        # Minimal state that managers may read
        self.world_seed: int = 42
        self.visited_sectors: set[tuple[int, int]] = {(0, 0)}
        self.land_sectors: set[tuple[int, int]] = {(0, 0)}
        self.sky_revealed_sectors: set[tuple[int, int]] = set()
        self.portal_quests: dict[str | tuple, dict] = {}
        self.treasure_reveals: list[dict] = []
        self.death_challenges: dict[int, dict] = {}
        self._sign_display: dict[int, dict | None] = {1: None, 2: None}
        self._sky_anim: dict[int, dict | None] = {1: None, 2: None}
        self._confirm_quit: bool = False
        self.running: bool = True

        # Lightweight SectorManager stand-in
        from src.world.sector_manager import SectorManager

        self.sectors = SectorManager(self, self.world_seed)
        self.sectors.visited_sectors = self.visited_sectors
        self.sectors.land_sectors = self.land_sectors
        self.sectors.sky_revealed_sectors = self.sky_revealed_sectors

        # Lightweight PortalManager stand-in
        from src.world.portal_manager import PortalManager

        self.portals = PortalManager(self)
        self.portal_quests = self.portals.portal_quests
        self.portal_warp = self.portals.portal_warp

    # ------------------------------------------------------------------
    # Helpers that managers expect on the game object
    # ------------------------------------------------------------------

    def get_scene(self, key: str | tuple) -> MapScene | None:
        scene = self.maps.get(key)
        return scene if isinstance(scene, MapScene) else None

    def get_map(self, key: str | tuple) -> GameMap | None:
        scene = self.maps.get(key)
        if isinstance(scene, MapScene):
            return object.__getattribute__(scene, "map")
        if isinstance(scene, GameMap):
            return scene
        return None

    def get_player_current_map(self, player: Player) -> GameMap | None:
        return self.get_map(player.current_map)

    def _snap_camera_to_player(self, player: Player) -> None:
        pass  # no-op in tests

    def _is_in_housing_env(self, player: Player) -> bool:
        key = player.current_map
        return (
            isinstance(key, tuple)
            and len(key) >= 3
            and key[0] in ("house", "house_sub")
        )

    def _get_player_sector(self, player: Player) -> tuple[int, int] | None:
        key = player.current_map
        if key == "overland" or key == ("sector", 0, 0):
            return (0, 0)
        if isinstance(key, tuple) and len(key) == 3 and key[0] == "sector":
            return (key[1], key[2])
        return None


@pytest.fixture()
def mock_game(mock_scene: MapScene, player1: Player, player2: Player) -> MockGame:
    """A ready-to-use MockGame with one overland scene and two players."""
    return MockGame(mock_scene, player1, player2)
