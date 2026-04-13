"""Sector management — generation, transitions, eviction, biome checks, wipe animation.

Extracted from game.py.  Owns sector-level world state and transition logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.config import (
    TILE,
    SECTOR_WIPE_DURATION,
    BiomeType,
    PORTAL_LAVA,
)
from src.data import ARMOR_PIECES, ArmorMaterial, TILE_INFO
from src.effects import FloatingText
from src.world import generate_ocean_sector, spawn_enemies, get_sector_biome
from src.world.map import GameMap
from src.world.scene import MapScene

if TYPE_CHECKING:
    from src.entities.player import Player


class SectorManager:
    """Manages sectors: generation, transitions, eviction, biome checks, wipe FX.

    Owns the following state (previously on Game):
    * ``visited_sectors``
    * ``land_sectors``
    * ``sky_revealed_sectors``
    * ``world_seed``
    * ``_entity_archive``
    * ``_sector_thumbnail_cache``
    * ``_biome_warn_timers``
    * ``sector_wipe``
    """

    def __init__(self, game: object, world_seed: int) -> None:
        self.game = game
        self.world_seed: int = world_seed

        self.visited_sectors: set[tuple[int, int]] = {(0, 0)}
        self.land_sectors: set[tuple[int, int]] = {(0, 0)}
        self.sky_revealed_sectors: set[tuple[int, int]] = set()

        self._entity_archive: dict[str | tuple, dict] = {}
        self._sector_thumbnail_cache: dict[tuple, pygame.Surface] = {}
        self._biome_warn_timers: dict[int, dict | None] = {1: None, 2: None}
        self.sector_wipe: dict[int, dict] = {}

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_player_sector(player: "Player") -> tuple[int, int] | None:
        """Return (sx, sy) for the player's current map, or None if underground."""
        key = player.current_map
        if key == "overland" or key == ("sector", 0, 0):
            return (0, 0)
        if isinstance(key, tuple) and len(key) == 3 and key[0] == "sector":
            return (key[1], key[2])
        return None

    @staticmethod
    def get_sector_coords(map_key: str | tuple) -> tuple[int, int] | None:
        """Return (sx, sy) for a surface map key, or None."""
        if map_key == "overland":
            return (0, 0)
        if isinstance(map_key, tuple) and len(map_key) == 3 and map_key[0] == "sector":
            return (map_key[1], map_key[2])
        return None

    # ------------------------------------------------------------------
    # Generation / eviction
    # ------------------------------------------------------------------

    def get_or_generate_sector(self, sx: int, sy: int) -> MapScene:
        """Return (or lazily generate) the MapScene for sector (sx, sy)."""
        game = self.game
        if sx == 0 and sy == 0:
            return game.maps["overland"]
        key = ("sector", sx, sy)
        if key not in game.maps:
            world_data, has_island, biome = generate_ocean_sector(
                sx, sy, self.world_seed
            )
            sector_map = GameMap(world_data, tileset="overland")
            sector_map.biome = biome
            sector_map.enemies = spawn_enemies(world_data, biome)
            sector_scene = MapScene(sector_map)
            game.maps[key] = sector_scene
            if has_island:
                self.land_sectors.add((sx, sy))
                game.portals.assign_portal_quest(key)
                game.portals.place_portal_on_map(sector_map, key)
                if biome == BiomeType.STANDARD:
                    from src.world.environments import OverlandEnvironment

                    land_env = OverlandEnvironment(map_key=key)
                    sector_scene.creatures.extend(land_env.spawn_creatures(sector_map))
            archived = self._entity_archive.pop(key, None)
            if archived:
                from src.save import (
                    _deserialize_worker,
                    _deserialize_pet,
                    _deserialize_creature,
                )

                sector_scene.workers.extend(
                    _deserialize_worker(w) for w in archived.get("workers", [])
                )
                sector_scene.pets.extend(
                    _deserialize_pet(p) for p in archived.get("pets", [])
                )
                sector_scene.creatures.extend(
                    _deserialize_creature(c) for c in archived.get("creatures", [])
                )
        return game.maps[key]

    def evict_distant_sectors(self) -> None:
        """Drop sector maps >2 sectors from all players."""
        game = self.game
        sectors_in_use: set[tuple[int, int]] = set()
        for player in (game.player1, game.player2):
            coords = self.get_player_sector(player)
            if coords is None:
                continue
            sx, sy = coords
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    sectors_in_use.add((sx + dx, sy + dy))

        to_evict: list[tuple] = []
        for key in game.maps:
            if isinstance(key, tuple) and len(key) == 3 and key[0] == "sector":
                if key[1] != 0 or key[2] != 0:
                    if (key[1], key[2]) not in sectors_in_use:
                        to_evict.append(key)
        for key in to_evict:
            scene = game.maps.get(key)
            if isinstance(scene, MapScene):
                from src.save import (
                    _serialize_worker,
                    _serialize_pet,
                    _serialize_creature,
                )

                self._entity_archive[key] = {
                    "workers": [_serialize_worker(w) for w in scene.workers],
                    "pets": [_serialize_pet(p) for p in scene.pets],
                    "creatures": [_serialize_creature(c) for c in scene.creatures],
                }
            del game.maps[key]

    # ------------------------------------------------------------------
    # Sky reveal
    # ------------------------------------------------------------------

    def reveal_sky_sectors(self, player: "Player") -> None:
        """Reveal a 5-sector radius around the player's current sector."""
        game = self.game
        sector = self.get_player_sector(player)
        if sector is None:
            return
        cx, cy = sector
        RADIUS = 5
        for dx in range(-RADIUS, RADIUS + 1):
            for dy in range(-RADIUS, RADIUS + 1):
                sx, sy = cx + dx, cy + dy
                self.sky_revealed_sectors.add((sx, sy))
                key = ("sector", sx, sy)
                if key not in game.maps:
                    world_data, has_island, biome = generate_ocean_sector(
                        sx, sy, self.world_seed
                    )
                    sector_map = GameMap(world_data, tileset="overland")
                    sector_map.biome = biome
                    sector_map.enemies = spawn_enemies(world_data, biome)
                    scene = MapScene(sector_map)
                    game.maps[key] = scene
                    if has_island:
                        self.land_sectors.add((sx, sy))
                        if key not in game.portal_quests:
                            game.portals.assign_portal_quest(key)
                            game.portals.place_portal_on_map(sector_map, key)
                        if biome == BiomeType.STANDARD:
                            from src.world.environments import OverlandEnvironment

                            env = OverlandEnvironment(map_key=key)
                            scene.creatures.extend(env.spawn_creatures(sector_map))

    # ------------------------------------------------------------------
    # Sector transitions
    # ------------------------------------------------------------------

    def check_sector_transitions(self, player: "Player") -> None:
        """Detect boundary crossing and teleport player to the adjacent sector."""
        if not player.on_boat:
            return
        sector_coords = self.get_player_sector(player)
        if sector_coords is None:
            return

        game = self.game
        sx, sy = sector_coords
        current_map = self.get_or_generate_sector(sx, sy)
        world_pixel_w = current_map.cols * TILE
        world_pixel_h = current_map.rows * TILE

        x, y = player.x, player.y
        pid = player.player_id
        direction: str | None = None
        new_sx, new_sy = sx, sy
        new_x, new_y = x, y

        margin = TILE // 2

        if x < margin:
            direction = "left"
            new_sx = sx - 1
            new_x = float(world_pixel_w - TILE)
            new_y = y
        elif x > world_pixel_w - margin:
            direction = "right"
            new_sx = sx + 1
            new_x = float(TILE)
            new_y = y
        elif y < margin:
            direction = "up"
            new_sy = sy - 1
            new_x = x
            new_y = float(world_pixel_h - TILE)
        elif y > world_pixel_h - margin:
            direction = "down"
            new_sy = sy + 1
            new_x = x
            new_y = float(TILE)

        if direction is None:
            return

        self.get_or_generate_sector(new_sx, new_sy)

        new_key: str | tuple = (
            ("sector", new_sx, new_sy) if (new_sx != 0 or new_sy != 0) else "overland"
        )
        player.current_map = new_key
        player.x = new_x
        player.y = new_y
        game._snap_camera_to_player(player)

        self.visited_sectors.add((new_sx, new_sy))

        if (new_sx, new_sy) in self.land_sectors and new_sx != 0 and new_sy != 0:
            biome = get_sector_biome(self.world_seed, new_sx, new_sy)
            if not self.check_biome_entry_armor(player, biome):
                _BIOME_WARNINGS = {
                    BiomeType.TUNDRA: "Too cold! Equip armor!",
                    BiomeType.VOLCANO: "Too hot! Full armor set needed!",
                }
                msg = _BIOME_WARNINGS.get(biome)
                if msg:
                    game.floats.append(
                        FloatingText(
                            int(player.x),
                            int(player.y) - 30,
                            msg,
                            (100, 200, 255),
                            player.current_map,
                        )
                    )
                    self._biome_warn_timers[pid] = {"biome": biome, "frames": 120}
            else:
                self._biome_warn_timers[pid] = None
        else:
            self._biome_warn_timers[pid] = None

        if not player.on_boat:
            self.sector_wipe[pid] = {
                "progress": 0.0,
                "direction": direction,
            }

        self.evict_distant_sectors()

    # ------------------------------------------------------------------
    # Biome / armor checks
    # ------------------------------------------------------------------

    @staticmethod
    def check_biome_entry_armor(player: "Player", biome: BiomeType) -> bool:
        """Return True if the player meets the armor requirement for *biome*."""
        body_slots = ["helmet", "chest", "legs", "boots"]
        if biome == BiomeType.TUNDRA:
            return any(player.equipment.get(s) is not None for s in body_slots)
        if biome == BiomeType.VOLCANO:
            return all(player.equipment.get(s) is not None for s in body_slots)
        return True

    @staticmethod
    def has_ancient_armor(player: "Player") -> bool:
        """Return True if the player has at least one Ancient armor piece equipped."""
        body_slots = ["helmet", "chest", "legs", "boots"]
        for slot in body_slots:
            item_name = player.equipment.get(slot)
            if (
                item_name
                and ARMOR_PIECES.get(item_name, {}).get("material")
                == ArmorMaterial.ANCIENT
            ):
                return True
        return False

    # ------------------------------------------------------------------
    # Thumbnails
    # ------------------------------------------------------------------

    def generate_sector_thumbnail(self, sx: int, sy: int) -> pygame.Surface | None:
        """Return (or build) an 80x60 thumbnail for sector (sx, sy)."""
        key = ("sector", sx, sy)
        if key in self._sector_thumbnail_cache:
            return self._sector_thumbnail_cache[key]
        scene = self.game.maps.get(key)
        if scene is None:
            return None
        thumb = pygame.Surface((scene.cols, scene.rows))
        for r in range(scene.rows):
            for c in range(scene.cols):
                tid = scene.get_tile(r, c)
                color = TILE_INFO.get(tid, {}).get("color", (50, 50, 50))
                thumb.set_at((c, r), color)
        self._sector_thumbnail_cache[key] = thumb
        return thumb

    # ------------------------------------------------------------------
    # Frame ticks (called from Game.update)
    # ------------------------------------------------------------------

    def tick_wipe(self, dt: float) -> None:
        """Advance sector-wipe animation timers."""
        for pid in list(self.sector_wipe.keys()):
            self.sector_wipe[pid]["progress"] += dt / SECTOR_WIPE_DURATION
            if self.sector_wipe[pid]["progress"] >= 1.0:
                del self.sector_wipe[pid]

    def tick_biome_damage(self, dt: float) -> None:
        """Tick biome entry damage timers and apply damage when expired."""
        game = self.game
        for player in (game.player1, game.player2):
            if player.is_dead:
                continue
            pid = player.player_id
            warn = self._biome_warn_timers[pid]
            if warn is None:
                continue
            warn["frames"] -= dt
            if warn["frames"] <= 0:
                if not self.check_biome_entry_armor(player, warn["biome"]):
                    player.take_damage(
                        5, game.particles, game.floats, player.current_map
                    )
                    if player.hp <= 0 and not player.is_dead:
                        game.death_challenge.start(player)
                self._biome_warn_timers[pid] = None

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_sector_wipe_viewport(
        self,
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
        progress: float,
    ) -> None:
        """Draw a white flash overlay during sector boundary crossing."""
        alpha = int(255 * (1.0 - abs(progress - 0.5) * 2.0))
        alpha = max(0, min(255, alpha))
        if alpha == 0:
            return
        flash = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
        flash.fill((220, 240, 255, alpha))
        self.game.screen.blit(flash, (screen_x, screen_y))
