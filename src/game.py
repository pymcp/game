"""Main game class and orchestration."""

import pygame
import math
import random
from src.config import (
    SCREEN_W,
    SCREEN_H,
    TILE,
    FPS,
    BG,
    WORLD_COLS,
    WORLD_ROWS,
    GRASS,
    DIRT,
    MOUNTAIN,
    TREE,
    WATER,
    HOUSE,
    IRON_ORE,
    GOLD_ORE,
    DIAMOND_ORE,
    CAVE_MOUNTAIN,
    CAVE_HILL,
    CAVE_EXIT,
    PIER,
    BOAT,
    TREASURE_CHEST,
    SAND,
    CORAL,
    REEF,
    DIVE_EXIT,
    PORTAL_RUINS,
    PORTAL_ACTIVE,
    ANCIENT_STONE,
    PORTAL_WALL,
    PORTAL_FLOOR,
    WOOD_FLOOR,
    WORKTABLE,
    HOUSE_EXIT,
    SETTLEMENT_HOUSE,
    SCUBA_BUILD_COST,
    SETTLEMENT_TIER_SIZES,
    SETTLEMENT_TIER_NAMES,
    HOUSE_BUILD_COST,
    PIER_BUILD_COST,
    BOAT_BUILD_COST,
    SECTOR_WIPE_DURATION,
    PORTAL_WARP_DURATION,
    BiomeType,
    PORTAL_LAVA,
    SIGN,
    BROKEN_LADDER,
    SKY_LADDER,
)
from src.data import (
    TILE_INFO,
    WEAPONS,
    PICKAXES,
    UPGRADE_COSTS,
    WEAPON_UNLOCK_COSTS,
    RECIPES,
    PortalQuestType,
    ARMOR_PIECES,
    ACCESSORY_PIECES,
    ARMOR_SLOT_ORDER,
    SLOT_LABELS,
    item_fits_slot,
    AccessoryEffect,
    ArmorMaterial,
)
from src.world import (
    generate_world,
    generate_ocean_sector,
    get_sector_biome,
    spawn_enemies,
    try_spend,
    has_adjacent_house,
    compute_town_clusters,
)
from src.world.map import GameMap
from src.world.scene import MapScene
from src.world.environments import (
    CaveEnvironment,
    UnderwaterEnvironment,
    PortalRealmEnvironment,
    HousingEnvironment,
    OverlandEnvironment,
)
from src.entities import Player, Projectile, Worker, Pet, Enemy, SeaCreature, Creature, OverlandCreature
from src.entities.player import CONTROL_SCHEME_PLAYER1, CONTROL_SCHEME_PLAYER2
from src.effects import Particle, FloatingText
from src.save import save_game, load_game, apply_save


class _EffectRouter:
    """Fake list whose `append`/`extend` route items to the correct MapScene.

    This lets the 60+ `self.floats.append(...)` and `self.particles.append(...)`
    call-sites remain unchanged while the effects are co-located with their map.
    The router holds a reference to a routing function supplied by the Game instance.
    """

    __slots__ = ("_route",)

    def __init__(self, route_fn) -> None:
        self._route = route_fn

    def append(self, item) -> None:
        self._route(item)

    def extend(self, items) -> None:
        for item in items:
            self._route(item)


class Game:
    """Main game class managing all game state and the main loop (2 players)."""

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)
        pygame.display.set_caption("Mining Game - 2 Players (F11 for fullscreen)")
        self.clock = pygame.time.Clock()
        self.is_fullscreen = False
        self.font = pygame.font.SysFont("monospace", 16)

        # Load sprite sheets; entities fall back to procedural draw if absent.
        import os as _os
        from src.rendering.registry import SpriteRegistry
        _sprites_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "assets", "sprites")
        SpriteRegistry.get_instance().load_all(_sprites_dir)

        # UI fonts — cached once to avoid re-creating every frame
        self.font_ui_sm = pygame.font.Font(None, 22)
        self.font_ui_xs = pygame.font.Font(None, 16)
        self.font_dc_big = pygame.font.SysFont("monospace", 38, bold=True)
        self.font_dc_med = pygame.font.SysFont("monospace", 26, bold=True)
        self.font_dc_sm = pygame.font.SysFont("monospace", 18)

        # Dynamic viewport dimensions (updated each frame from actual screen size)
        self.viewport_w = SCREEN_W // 2
        self.viewport_h = SCREEN_H

        # Map system - store all maps by key
        # "overland" is the main map, caves are keyed by (col, row)
        world_data = generate_world()
        overland_gmap = GameMap(world_data, tileset="overland")
        # Seed enemies before wrapping so MapScene transfers them immediately.
        overland_gmap.enemies = spawn_enemies(overland_gmap.world)
        overland_scene = MapScene(overland_gmap)
        # Spawn land creatures on the home island into the overland scene.
        home_env = OverlandEnvironment(map_key="overland")
        overland_scene.creatures.extend(home_env.spawn_creatures(overland_gmap))
        self.maps: dict[str | tuple, MapScene] = {"overland": overland_scene}

        # Convenience local alias (tile access still works via MapScene proxy).
        overland_map = overland_scene

        # Two Players - find grass tiles near center
        def find_grass_spawn(offset_x):
            """Find a grass tile near center offset by offset_x."""
            start_col = (WORLD_COLS // 2) + (offset_x // TILE)
            start_row = WORLD_ROWS // 2

            # Search in expanding square around target position
            for search_dist in range(10):
                for dc in range(-search_dist, search_dist + 1):
                    for dr in range(-search_dist, search_dist + 1):
                        if abs(dc) != search_dist and abs(dr) != search_dist:
                            continue
                        col = start_col + dc
                        row = start_row + dr
                        if 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS:
                            if overland_map.get_tile(row, col) == GRASS:
                                return col * TILE + TILE // 2, row * TILE + TILE // 2
            # Fallback to center if no grass found
            return (WORLD_COLS // 2) * TILE + TILE // 2, (
                WORLD_ROWS // 2
            ) * TILE + TILE // 2

        start_x1, start_y1 = find_grass_spawn(-TILE)
        start_x2, start_y2 = find_grass_spawn(TILE)

        self.player1 = Player(
            start_x1, start_y1, player_id=1, control_scheme=CONTROL_SCHEME_PLAYER1
        )
        self.player2 = Player(
            start_x2, start_y2, player_id=2, control_scheme=CONTROL_SCHEME_PLAYER2
        )

        # Cameras (one for each player's viewport)
        self.cam1_x = self.player1.x - self.viewport_w // 2
        self.cam1_y = self.player1.y - self.viewport_h // 2
        self.cam2_x = self.player2.x - self.viewport_w // 2
        self.cam2_y = self.player2.y - self.viewport_h // 2

        # Entity archive: evicted sector entities saved by map key for restoration.
        self._entity_archive: dict[str | tuple, dict] = {}

        # Effect routers: self.floats.append(f) and self.particles.append(p) route
        # to the appropriate MapScene so all 60+ call-sites need not change.
        self.floats: _EffectRouter = _EffectRouter(self._add_float)
        self.particles: _EffectRouter = _EffectRouter(self._add_particle)

        self.running = True

        # Death challenge state: {player_id: {"question": str, "answer": int, "input": str, "wrong": bool}}
        self.death_challenges = {}

        # Crafting menu state: player_id → cursor index (None = closed)
        self.craft_menus: dict[int, int | None] = {1: None, 2: None}

        # Equipment menu state: player_id → {"slot_idx": int, "sub_idx": int|None} or None
        self.equip_menus: dict[int, dict | None] = {1: None, 2: None}

        # Portal quest state: map_key → quest dict
        # {"type": PortalQuestType, "restored": bool, ...type-specific keys}
        self.portal_quests: dict[str | tuple, dict] = {}

        # Treasure reveal state: [{"player_id": int, "items": dict, "timer": float}]
        self.treasure_reveals = []

        # Deterministic seed for the ocean sector grid
        self.world_seed = random.randint(0, 0xFFFF_FFFF)
        # Alias sector (0,0) as the home overland map so sector logic can use one key type
        self.maps[("sector", 0, 0)] = self.maps["overland"]
        # Sector-wipe animation state: {player_id: {"progress": float, "direction": str}}
        self.sector_wipe = {}
        # Portal-warp vortex animation state: {player_id: {"progress": float}}
        self.portal_warp: dict[int, dict] = {}
        # Biome entry damage: {player_id: {"biome": BiomeType, "frames": int} | None}
        self._biome_warn_timers: dict[int, dict | None] = {1: None, 2: None}
        # Portal lava hurt cooldown: {player_id: int} (frames until next lava damage tick)
        self._lava_hurt_timers: dict[int, int] = {1: 0, 2: 0}
        # Biome entry damage: {player_id: {"biome": BiomeType, "frames": int} | None}
        self._biome_warn_timers: dict[int, dict | None] = {1: None, 2: None}
        # Portal lava hurt cooldown: {player_id: int} (counts down frames between damage ticks)
        self._lava_hurt_timers: dict[int, int] = {1: 0, 2: 0}
        # Mount state: which Creature each player is currently riding (None = none)
        self._player_mounts: dict[int, Creature | None] = {1: None, 2: None}
        # Set of (sx, sy) sector coordinates the players have ever visited
        self.visited_sectors: set = {(0, 0)}
        # Set of (sx, sy) sector coordinates that contain land (grass tiles)
        self.land_sectors: set = {(0, 0)}

        # Sky-ladder quest state
        self._sky_view: dict[int, bool] = {1: False, 2: False}
        # phase: "ascend" | "sky" | "descend" | None; progress: 0.0 → 1.0 (ticks)
        self._sky_anim: dict[int, dict | None] = {1: None, 2: None}
        self._sky_clouds: list[dict] = []
        self._sector_thumbnail_cache: dict[tuple, pygame.Surface] = {}
        # Per-player sign text popup: {text: str, timer: float (seconds)}
        self._sign_display: dict[int, dict | None] = {1: None, 2: None}
        # Set of (sx, sy) coords revealed by the sky view (visible on minimap even if unvisited)
        self.sky_revealed_sectors: set = set()

        # Load saved state if a save file exists
        save_data = load_game()
        if save_data is not None:
            apply_save(self, save_data)

        # Place/verify portal ruins on the overland map (skip if loaded from save)
        if "overland" not in self.portal_quests:
            self._assign_portal_quest("overland")
            self._place_portal_on_map(self.maps["overland"], "overland")

        # Place broken ladder + sign on the overland map (new game only)
        if save_data is None:
            self._place_sky_ladder_quest(self.maps["overland"])

    # -- death challenge ---------------------------------------------------

    def _start_death_challenge(self, player: Player) -> None:
        """Pause a dead player and present a math problem they must solve to respawn."""
        player.is_dead = True
        player.hurt_timer = 0
        a = random.randint(1, 20)
        b = random.randint(1, 20)
        if random.choice([True, False]):
            answer = a + b
            question = f"{a} + {b} = ?"
        else:
            if a < b:
                a, b = b, a
            answer = a - b
            question = f"{a} - {b} = ?"
        self.death_challenges[player.player_id] = {
            "question": question,
            "answer": answer,
            "input": "",
            "wrong": False,
        }

    def _submit_death_challenge(self, player: Player) -> None:
        """Check the typed answer; respawn player on correct answer."""
        challenge = self.death_challenges.get(player.player_id)
        if challenge is None:
            return
        try:
            typed = int(challenge["input"])
        except ValueError:
            challenge["wrong"] = True
            challenge["input"] = ""
            return
        if typed == challenge["answer"]:
            player.is_dead = False
            player.hp = player.max_hp
            del self.death_challenges[player.player_id]
            self._respawn_player(player)
            self.floats.append(
                FloatingText(
                    player.x,
                    player.y - 30,
                    "Respawned!",
                    (100, 255, 100),
                    player.current_map,
                )
            )
        else:
            challenge["wrong"] = True
            challenge["input"] = ""

    def _respawn_player(self, player: Player) -> None:
        """Teleport a respawning player to a safe grass tile near the world centre."""
        # If this player has exited a portal before, respawn there instead
        if (
            player.last_portal_exit_map is not None
            and player.last_portal_exit_x is not None
            and player.last_portal_exit_map in self.maps
        ):
            player.current_map = player.last_portal_exit_map
            player.x = player.last_portal_exit_x
            player.y = player.last_portal_exit_y
            self._snap_camera_to_player(player)
            return
        player.current_map = "overland"
        overland = self.maps["overland"]
        for search_dist in range(1, 30):
            for dc in range(-search_dist, search_dist + 1):
                for dr in range(-search_dist, search_dist + 1):
                    if abs(dc) != search_dist and abs(dr) != search_dist:
                        continue
                    col = WORLD_COLS // 2 + dc
                    row = WORLD_ROWS // 2 + dr
                    if 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS:
                        if overland.get_tile(row, col) == GRASS:
                            player.x = col * TILE + TILE // 2
                            player.y = row * TILE + TILE // 2
                            return
        player.x = WORLD_COLS // 2 * TILE + TILE // 2
        player.y = WORLD_ROWS // 2 * TILE + TILE // 2

    # -- portal quests -----------------------------------------------------

    def _assign_portal_quest(self, map_key: str | tuple) -> dict:
        """Deterministically assign a portal quest for the given map key.

        Uses a seeded RNG derived from (world_seed, map_key) so island quests
        are consistent across sessions.  Stores the result in portal_quests and
        returns the quest dict.
        """
        seed = hash((self.world_seed, str(map_key))) & 0xFFFF_FFFF
        rng = random.Random(seed)
        quest_type = rng.choice(list(PortalQuestType))

        if quest_type == PortalQuestType.RITUAL:
            quest: dict = {
                "type": PortalQuestType.RITUAL,
                "restored": False,
                "stones_total": 4,
                "stones_activated": 0,
            }
        elif quest_type == PortalQuestType.GATHER:
            # Scale cost by island distance from (0, 0)
            if (
                isinstance(map_key, tuple)
                and len(map_key) == 3
                and map_key[0] == "sector"
            ):
                dist = abs(map_key[1]) + abs(map_key[2])
            else:
                dist = 0
            gold_needed = max(5, 5 + dist)
            diamond_needed = max(2, dist)
            quest = {
                "type": PortalQuestType.GATHER,
                "restored": False,
                "required": {"Gold": gold_needed, "Diamond": diamond_needed},
            }
        else:  # combat
            quest = {
                "type": PortalQuestType.COMBAT,
                "restored": False,
                "guardian_defeated": False,
                "guardian_spawned": False,
            }

        self.portal_quests[map_key] = quest
        return quest

    def _place_portal_on_map(self, game_map: "GameMap", map_key: str | tuple) -> None:
        """Place portal tiles on a newly generated island map.

        Finds a GRASS tile sufficiently far from the map centre, places
        PORTAL_RUINS (or PORTAL_ACTIVE if the quest is already restored),
        and sets up ritual stones or combat guardian flags.
        """
        quest = self.portal_quests.get(map_key)
        if quest is None:
            return

        seed = hash((self.world_seed, str(map_key), "place")) & 0xFFFF_FFFF
        rng = random.Random(seed)

        rows, cols = game_map.rows, game_map.cols
        cx, cy = cols // 2, rows // 2
        min_dist = 12

        # Collect candidate GRASS tiles far enough from centre
        candidates = [
            (c, r)
            for r in range(rows)
            for c in range(cols)
            if game_map.get_tile(r, c) == GRASS
            and abs(c - cx) + abs(r - cy) >= min_dist
        ]
        if not candidates:
            # Fallback: any grass tile
            candidates = [
                (c, r)
                for r in range(rows)
                for c in range(cols)
                if game_map.get_tile(r, c) == GRASS
            ]
        if not candidates:
            return

        rng.shuffle(candidates)
        portal_col, portal_row = candidates[0]

        tile_id = PORTAL_ACTIVE if quest["restored"] else PORTAL_RUINS
        game_map.set_tile(portal_row, portal_col, tile_id)
        game_map.portal_col = portal_col
        game_map.portal_row = portal_row

        # Ritual: scatter ANCIENT_STONE tiles around the island
        if quest["type"] == PortalQuestType.RITUAL:
            stone_candidates = [
                (c, r)
                for r in range(rows)
                for c in range(cols)
                if game_map.get_tile(r, c) == GRASS
                and (c, r) != (portal_col, portal_row)
                and abs(c - cx) + abs(r - cy) >= 8
            ]
            rng.shuffle(stone_candidates)
            positions: list[tuple[int, int]] = []
            for sc, sr in stone_candidates:
                # Ensure stones are spread out (at least 8 tiles apart from each other)
                if all(abs(sc - ec) + abs(sr - er) >= 8 for ec, er in positions):
                    game_map.set_tile(sr, sc, ANCIENT_STONE)
                    positions.append((sc, sr))
                    if len(positions) >= quest["stones_total"]:
                        break
            game_map.ritual_stone_positions = positions

        # Combat: flag that the sentinel has not yet been spawned
        if quest["type"] == PortalQuestType.COMBAT:
            game_map.portal_guardian_spawned = quest.get("guardian_spawned", False)

    def _place_sky_ladder_quest(self, game_map: "MapScene") -> None:
        """Place the broken ladder and sign on the overland map for a new game.

        Scans outward from the map centre for a GRASS tile that has another
        GRASS tile immediately to its left, and places SIGN there and
        BROKEN_LADDER one tile to the right.
        """
        rows, cols = game_map.rows, game_map.cols
        cx, cy = cols // 2, rows // 2

        placed = False
        for dist in range(4, min(cx, cy)):
            for r in range(max(1, cy - dist), min(rows - 1, cy + dist + 1)):
                for c in range(max(2, cx - dist), min(cols - 1, cx + dist + 1)):
                    if (
                        game_map.get_tile(r, c) == GRASS
                        and game_map.get_tile(r, c - 1) == GRASS
                    ):
                        sign_col, sign_row = c - 1, r
                        ladder_col, ladder_row = c, r
                        game_map.set_tile(sign_row, sign_col, SIGN)
                        game_map.set_tile(ladder_row, ladder_col, BROKEN_LADDER)
                        raw = object.__getattribute__(game_map, "map")
                        raw.sign_texts[(sign_col, sign_row)] = (
                            "This old ladder once reached the sky.\n"
                            "Repair it with:\n"
                            "  \u2022 30 Diamond\n"
                            "  \u2022 30 Stone\n"
                            "  \u2022 30 Wood"
                        )
                        raw.ladder_repaired = False
                        raw.ladder_col = ladder_col
                        raw.ladder_row = ladder_row
                        placed = True
                        break
                if placed:
                    break
            if placed:
                break

    # ------------------------------------------------------------------
    # Sky-view helpers
    # ------------------------------------------------------------------

    # Ladder repair cost
    _SKY_LADDER_COST: dict[str, int] = {
        "Diamond": 30,
        "Stone": 30,
        "Wood": 30,
    }

    def _enter_sky_view(self, player: Player) -> None:
        """Begin the ascend animation for *player*, then show the sky view."""
        pid = player.player_id
        self._sky_view[pid] = True
        self._sky_anim[pid] = {"phase": "ascend", "progress": 0.0}
        self._reveal_sky_sectors(player)
        if not self._sky_clouds:
            self._init_sky_clouds()

    def _exit_sky_view(self, player: Player) -> None:
        """Begin the descend animation for *player*, closing the sky view."""
        pid = player.player_id
        anim = self._sky_anim[pid]
        if anim is not None and anim["phase"] == "sky":
            # Transition to descend
            self._sky_anim[pid] = {"phase": "descend", "progress": 0.0}
        else:
            # Already animating — skip straight to closed
            self._sky_view[pid] = False
            self._sky_anim[pid] = None

    def _reveal_sky_sectors(self, player: Player) -> None:
        """Reveal a 5-sector radius around the player's current sector.

        Land sectors within that radius are generated immediately so
        that thumbnails can be built.  Ocean sectors are revealed in
        the minimap but not materialised (they need no entities).
        """
        sector = self._get_player_sector(player)
        if sector is None:
            return
        cx, cy = sector
        RADIUS = 5
        for dx in range(-RADIUS, RADIUS + 1):
            for dy in range(-RADIUS, RADIUS + 1):
                sx, sy = cx + dx, cy + dy
                self.sky_revealed_sectors.add((sx, sy))
                key = ("sector", sx, sy)
                if key not in self.maps:
                    # Generate the sector map (needed for thumbnail + entity spawning)
                    world_data, has_island, biome = generate_ocean_sector(sx, sy, self.world_seed)
                    sector_map = GameMap(world_data, tileset="overland")
                    sector_map.biome = biome
                    sector_map.enemies = spawn_enemies(world_data, biome)
                    scene = MapScene(sector_map)
                    self.maps[key] = scene
                    if has_island:
                        self.land_sectors.add((sx, sy))
                        if key not in self.portal_quests:
                            self._assign_portal_quest(key)
                            self._place_portal_on_map(sector_map, key)
                        if biome == BiomeType.STANDARD:
                            from src.world.environments import OverlandEnvironment
                            env = OverlandEnvironment(map_key=key)
                            scene.creatures.extend(env.spawn_creatures(sector_map))

    def _init_sky_clouds(self) -> None:
        """Populate the cloud layer with 8 randomly positioned cloud instances."""
        self._sky_clouds = []
        from src.rendering.registry import SpriteRegistry
        reg = SpriteRegistry.get_instance()
        cloud_entry = reg.get("cloud")
        n_frames = cloud_entry[1]["states"]["idle"]["frames"] if cloud_entry else 4
        for i in range(8):
            self._sky_clouds.append({
                "x": float(random.randint(0, 1920)),
                "y": float(random.randint(50, 900)),
                "speed": random.uniform(0.15, 0.45),
                "alpha": random.randint(70, 130),
                "frame": random.randint(0, n_frames - 1),
                "frame_timer": random.uniform(0.0, 2000.0),
            })

    def _generate_sector_thumbnail(self, sx: int, sy: int) -> pygame.Surface | None:
        """Return (or build) an 80×60 thumbnail Surface for sector (sx, sy).

        Each pixel represents one tile, coloured by TILE_INFO.
        Returns None if the sector map is not yet loaded.
        """
        key = ("sector", sx, sy)
        if key in self._sector_thumbnail_cache:
            return self._sector_thumbnail_cache[key]
        scene = self.maps.get(key)
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

    def _check_portal_restored(self, map_key: str | tuple) -> bool:
        """Evaluate whether a portal quest is complete and restore if so.

        Returns True if the portal is (now) restored.
        """
        quest = self.portal_quests.get(map_key)
        if quest is None:
            return False
        if quest["restored"]:
            return True

        complete = False
        if quest["type"] == PortalQuestType.RITUAL:
            complete = quest["stones_activated"] >= quest["stones_total"]
        elif quest["type"] == PortalQuestType.GATHER:
            complete = True  # gather completion is checked at delivery time
        elif quest["type"] == PortalQuestType.COMBAT:
            complete = quest.get("guardian_defeated", False)

        if complete:
            quest["restored"] = True
            game_map = self.maps.get(map_key)
            if game_map is not None and hasattr(game_map, "portal_col"):
                game_map.set_tile(
                    game_map.portal_row, game_map.portal_col, PORTAL_ACTIVE
                )
            return True
        return False

    # -- map / scene helpers -----------------------------------------------

    def get_scene(self, key: "str | tuple") -> "MapScene | None":
        """Return the MapScene for *key*, or None if not loaded."""
        scene = self.maps.get(key)
        if isinstance(scene, MapScene):
            return scene
        return None

    def get_map(self, key: "str | tuple") -> "GameMap | None":
        """Return the raw GameMap for *key*, or None if not loaded."""
        scene = self.maps.get(key)
        if isinstance(scene, MapScene):
            return object.__getattribute__(scene, "map")
        if isinstance(scene, GameMap):
            return scene
        return None

    def _add_float(self, f: "FloatingText") -> None:
        """Route a FloatingText to the correct scene's floats list."""
        key = f.map_key
        scene = self.maps.get(key)
        if scene is None:
            scene = self.maps.get("overland")
        if scene is not None:
            scene.floats.append(f)

    def _add_particle(self, p: "Particle") -> None:
        """Route a Particle to the correct scene's particles list."""
        key = p.map_key
        scene = self.maps.get(key)
        if scene is None:
            scene = self.maps.get("overland")
        if scene is not None:
            scene.particles.append(p)

    # -- main loop ---------------------------------------------------------

    def run(self) -> None:
        """Main game loop."""
        while self.running:
            dt = self.clock.tick(FPS) / 16.667
            self.handle_events()
            self.update(dt)
            self.draw()
        save_game(self)
        pygame.quit()

    # -- events ------------------------------------------------------------

    def handle_events(self) -> None:
        """Handle input events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)
            elif event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)

    def _handle_keydown(self, key: int) -> None:
        """Handle key press (for both players based on key)."""
        # --- Death challenge input handling (takes priority over all other keys) ---
        active_player = None
        if self.player1.is_dead and self.player1.player_id in self.death_challenges:
            active_player = self.player1
        elif self.player2.is_dead and self.player2.player_id in self.death_challenges:
            active_player = self.player2

        if active_player is not None:
            challenge = self.death_challenges[active_player.player_id]
            digit_map = {
                pygame.K_0: "0",
                pygame.K_1: "1",
                pygame.K_2: "2",
                pygame.K_3: "3",
                pygame.K_4: "4",
                pygame.K_5: "5",
                pygame.K_6: "6",
                pygame.K_7: "7",
                pygame.K_8: "8",
                pygame.K_9: "9",
                pygame.K_KP0: "0",
                pygame.K_KP1: "1",
                pygame.K_KP2: "2",
                pygame.K_KP3: "3",
                pygame.K_KP4: "4",
                pygame.K_KP5: "5",
                pygame.K_KP6: "6",
                pygame.K_KP7: "7",
                pygame.K_KP8: "8",
                pygame.K_KP9: "9",
            }
            if key in digit_map:
                challenge["input"] += digit_map[key]
                challenge["wrong"] = False
                return
            elif key in (pygame.K_MINUS, pygame.K_KP_MINUS) and not challenge["input"]:
                challenge["input"] = "-"
                challenge["wrong"] = False
                return
            elif key == pygame.K_BACKSPACE:
                challenge["input"] = challenge["input"][:-1]
                challenge["wrong"] = False
                return
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._submit_death_challenge(active_player)
                return

        # --- Equipment menu input (takes priority over normal keys while open) ---
        equip_consumed = False
        for player in (self.player1, self.player2):
            pid = player.player_id
            if self.equip_menus[pid] is None:
                continue
            state = self.equip_menus[pid]
            up_key = player.controls.move_keys["up"]
            down_key = player.controls.move_keys["down"]
            num_slots = len(ARMOR_SLOT_ORDER)
            if state["sub_idx"] is None:
                # Navigating the main slot list
                if key == up_key:
                    state["slot_idx"] = (state["slot_idx"] - 1) % num_slots
                    equip_consumed = True
                elif key == down_key:
                    state["slot_idx"] = (state["slot_idx"] + 1) % num_slots
                    equip_consumed = True
                elif key == player.controls.interact_key:
                    state["sub_idx"] = 0  # open sub-menu for this slot
                    equip_consumed = True
                elif key == pygame.K_ESCAPE or key == player.controls.equip_key:
                    self.equip_menus[pid] = None
                    equip_consumed = True
            else:
                # Navigating the sub-menu (compatible items + Unequip + Back)
                slot_key = ARMOR_SLOT_ORDER[state["slot_idx"]]
                options = self._equip_menu_options(player, slot_key)
                if key == up_key:
                    state["sub_idx"] = (state["sub_idx"] - 1) % len(options)
                    equip_consumed = True
                elif key == down_key:
                    state["sub_idx"] = (state["sub_idx"] + 1) % len(options)
                    equip_consumed = True
                elif key == player.controls.interact_key:
                    chosen = options[state["sub_idx"]]
                    tx, ty = int(player.x), int(player.y) - 20
                    if chosen == "_unequip":
                        player.unequip_item(slot_key)
                        self.floats.append(
                            FloatingText(
                                tx,
                                ty,
                                "Unequipped",
                                (200, 200, 100),
                                player.current_map,
                            )
                        )
                    elif chosen == "_back":
                        pass  # fall through to closing sub-menu
                    else:
                        if player.equip_item(slot_key, chosen):
                            self.floats.append(
                                FloatingText(
                                    tx,
                                    ty,
                                    f"Equipped {chosen}!",
                                    (100, 220, 100),
                                    player.current_map,
                                )
                            )
                    state["sub_idx"] = None
                    equip_consumed = True
                elif key == pygame.K_ESCAPE:
                    state["sub_idx"] = None
                    equip_consumed = True
        if equip_consumed:
            return

        # --- Crafting menu input (takes priority over normal keys while open) ---
        craft_consumed = False
        for player in (self.player1, self.player2):
            pid = player.player_id
            if self.craft_menus[pid] is None:
                continue
            cursor = self.craft_menus[pid]
            # Filter recipes to those available at the current housing tier
            current_map_obj = self.get_player_current_map(player)
            housing_tier = getattr(current_map_obj, "housing_tier", 0)
            available_recipes = [
                r for r in RECIPES if r.get("min_tier", 0) <= housing_tier
            ]
            total_entries = len(available_recipes) + 1  # recipes + "Close"
            # Clamp cursor in case the available list shrank
            cursor = min(cursor, total_entries - 1)
            self.craft_menus[pid] = cursor
            up_key = player.controls.move_keys["up"]
            down_key = player.controls.move_keys["down"]
            if key == up_key:
                self.craft_menus[pid] = (cursor - 1) % total_entries
                craft_consumed = True
            elif key == down_key:
                self.craft_menus[pid] = (cursor + 1) % total_entries
                craft_consumed = True
            elif key == player.controls.interact_key:
                if cursor < len(available_recipes):
                    recipe = available_recipes[cursor]
                    tx = int(player.x)
                    ty = int(player.y) - 20
                    cost_str = ", ".join(
                        f"{qty} {item}" for item, qty in recipe["cost"].items()
                    )
                    if try_spend(player.inventory, recipe["cost"]):
                        result = recipe["result"]
                        player.inventory[result["item"]] = (
                            player.inventory.get(result["item"], 0) + result["qty"]
                        )
                        self.floats.append(
                            FloatingText(
                                tx,
                                ty,
                                f"{result['qty']}x {result['item']}! (-{cost_str})",
                                (60, 200, 255),
                                player.current_map,
                            )
                        )
                        for _ in range(8):
                            self.particles.append(
                                Particle(tx, ty, (40, 160, 220), player.current_map)
                            )
                    else:
                        self.floats.append(
                            FloatingText(
                                tx,
                                ty,
                                f"Need {cost_str}!",
                                (255, 100, 100),
                                player.current_map,
                            )
                        )
                else:
                    # "Close" entry selected
                    self.craft_menus[pid] = None
                craft_consumed = True
            elif key == pygame.K_ESCAPE:
                self.craft_menus[pid] = None
                craft_consumed = True
        if craft_consumed:
            return

        if key == pygame.K_ESCAPE:
            self.running = False
        elif key == pygame.K_F11:
            self.is_fullscreen = not self.is_fullscreen
            if self.is_fullscreen:
                self.screen = pygame.display.set_mode(
                    (SCREEN_W, SCREEN_H), pygame.FULLSCREEN
                )
            else:
                self.screen = pygame.display.set_mode(
                    (SCREEN_W, SCREEN_H), pygame.RESIZABLE
                )
        # DEBUG: F8 spawns a 1×1 house and a 4×4 house cluster near player 1.
        elif key == pygame.K_F8:
            self._debug_spawn_houses(self.player1)
        # DEBUG: F9 instantly restores the portal on whichever island player 1 is on
        # and fills both players' inventories with all equippable items + materials.
        elif key == pygame.K_F9:
            self._debug_restore_portal(self.player1)
            self._debug_give_all_items()
        # Player 1 controls (blocked while dead)
        elif not self.player1.is_dead and key == self.player1.controls.upgrade_pick_key:
            self.player1.try_upgrade_pick()
        elif (
            not self.player1.is_dead and key == self.player1.controls.upgrade_weapon_key
        ):
            self.player1.try_upgrade_weapon()
        elif not self.player1.is_dead and key == self.player1.controls.build_house_key:
            self._try_build_house(self.player1)
        elif (
            not self.player1.is_dead
            and key == self.player1.controls.toggle_auto_mine_key
        ):
            self.player1.toggle_auto_mine()
        elif (
            not self.player1.is_dead
            and key == self.player1.controls.toggle_auto_fire_key
        ):
            self.player1.toggle_auto_fire()
        elif not self.player1.is_dead and key == self.player1.controls.interact_key:
            self._try_interact(self.player1)
        elif not self.player1.is_dead and key == self.player1.controls.build_pier_key:
            self._try_build_pier(self.player1)
        elif not self.player1.is_dead and key == self.player1.controls.equip_key:
            pid = self.player1.player_id
            self.equip_menus[pid] = (
                None if self.equip_menus[pid] else {"slot_idx": 0, "sub_idx": None}
            )
        # Player 2 controls (blocked while dead)
        elif not self.player2.is_dead and key == self.player2.controls.upgrade_pick_key:
            self.player2.try_upgrade_pick()
        elif (
            not self.player2.is_dead and key == self.player2.controls.upgrade_weapon_key
        ):
            self.player2.try_upgrade_weapon()
        elif not self.player2.is_dead and key == self.player2.controls.build_house_key:
            self._try_build_house(self.player2)
        elif (
            not self.player2.is_dead
            and key == self.player2.controls.toggle_auto_mine_key
        ):
            self.player2.toggle_auto_mine()
        elif (
            not self.player2.is_dead
            and key == self.player2.controls.toggle_auto_fire_key
        ):
            self.player2.toggle_auto_fire()
        elif not self.player2.is_dead and key == self.player2.controls.interact_key:
            self._try_interact(self.player2)
        elif not self.player2.is_dead and key == self.player2.controls.build_pier_key:
            self._try_build_pier(self.player2)
        elif not self.player2.is_dead and key == self.player2.controls.equip_key:
            pid = self.player2.player_id
            self.equip_menus[pid] = (
                None if self.equip_menus[pid] else {"slot_idx": 0, "sub_idx": None}
            )

    def _try_build_house(self, player: Player) -> None:
        """Attempt to build a house at player position."""
        # Only allow building on overland-tileset maps (blocks caves and underwater)
        current_map = self.maps[player.current_map]
        if current_map.tileset != "overland":
            return

        build_col = int(player.x) // TILE
        build_row = int(player.y) // TILE
        if not (0 <= build_col < WORLD_COLS and 0 <= build_row < WORLD_ROWS):
            return

        if (
            current_map.get_tile(build_row, build_col) != GRASS
            or player.inventory.get("Dirt", 0) < HOUSE_BUILD_COST
        ):
            return
        if not try_spend(player.inventory, {"Dirt": HOUSE_BUILD_COST}):
            return

        current_map.set_tile(build_row, build_col, HOUSE)
        current_map.set_tile_hp(build_row, build_col, 0)
        tile_cx = build_col * TILE + TILE // 2
        tile_cy = build_row * TILE + TILE // 2
        self.floats.append(
            FloatingText(
                tile_cx, tile_cy, "House built!", (210, 160, 60), player.current_map
            )
        )
        for _ in range(10):
            self.particles.append(
                Particle(tile_cx, tile_cy, (160, 82, 45), player.current_map)
            )

        home = player.current_map
        home_scene = self.maps.get(home)
        if random.random() < 0.25:
            if home_scene is not None:
                home_scene.pets.append(Pet(tile_cx, tile_cy, kind="dog", home_map=home))
            self.floats.append(
                FloatingText(
                    tile_cx,
                    tile_cy - 20,
                    "Dog spawned!",
                    (180, 130, 70),
                    player.current_map,
                )
            )
        else:
            workers_on_map = len(home_scene.workers) if home_scene is not None else 0
            if workers_on_map < 5:
                if home_scene is not None:
                    home_scene.workers.append(
                        Worker(tile_cx, tile_cy, player_id=player.player_id, home_map=home)
                    )
                self.floats.append(
                    FloatingText(
                        tile_cx,
                        tile_cy - 20,
                        "Worker spawned!",
                        (100, 220, 255),
                        player.current_map,
                    )
                )
            else:
                self.floats.append(
                    FloatingText(
                        tile_cx,
                        tile_cy - 20,
                        "Worker cap reached!",
                        (255, 160, 60),
                        player.current_map,
                    )
                )

        if has_adjacent_house(current_map.world, build_col, build_row):
            if home_scene is not None:
                home_scene.pets.append(Pet(tile_cx, tile_cy, kind="cat", home_map=home))
            self.floats.append(
                FloatingText(
                    tile_cx,
                    tile_cy - 36,
                    "Cat appeared!",
                    (255, 165, 0),
                    player.current_map,
                )
            )

        self._update_town_clusters(build_col, build_row, player, current_map)

    # -- helpers -----------------------------------------------------------

    def get_player_current_map(self, player: Player) -> GameMap | None:
        """Get the GameMap object that the player is currently on."""
        map_key = player.current_map
        if isinstance(map_key, tuple):
            return self.maps.get(map_key)
        return self.maps.get(map_key)

    def _find_grass_spawn(
        self, game_map: GameMap, prefer_col: int, prefer_row: int
    ) -> tuple[float, float]:
        """Return (x, y) pixel centre of the nearest GRASS tile to prefer_col/row."""
        rows = game_map.rows
        cols = game_map.cols
        for sd in range(max(rows, cols)):
            for dc in range(-sd, sd + 1):
                for dr in range(-sd, sd + 1):
                    if abs(dc) != sd and abs(dr) != sd:
                        continue
                    c = prefer_col + dc
                    r = prefer_row + dr
                    if 0 <= c < cols and 0 <= r < rows:
                        if game_map.get_tile(r, c) == GRASS:
                            return c * TILE + TILE // 2, r * TILE + TILE // 2
        return prefer_col * TILE + TILE // 2, prefer_row * TILE + TILE // 2

    # -- sailing / pier / boat / interaction --------------------------------

    def _try_interact(self, player: Player) -> None:
        """Context-sensitive interact key handler.

        Priority:
          0. Standing ON a HOUSE tile on a surface map → enter the housing environment.
          0.5. Inside a housing env adjacent to WORKTABLE → open craft menu.
          0.6. Inside a housing env standing on SETTLEMENT_HOUSE → enter sub-house.
          0.7. Inside a housing env standing on HOUSE_EXIT → exit housing env.
          1. If standing on a cave entrance → enter the cave.
          2. If in a cave and standing on a CAVE_EXIT tile → exit the cave.
          2.5. If in an underwater map and standing on DIVE_EXIT → surface.
          3. If player is on_boat → dive (with Scuba Gear) or show hint.
          4. If adjacent to a TREASURE_CHEST → open it.
          5. If standing on a PIER tile with WATER adjacent → build boat (if materials).
        """
        pid = player.player_id
        current_map_obj = self.get_player_current_map(player)
        if current_map_obj is None:
            return

        p_col = int(player.x) // TILE
        p_row = int(player.y) // TILE

        # 3.6 Sky-view exit — takes priority over everything else
        if self._sky_view[pid]:
            self._exit_sky_view(player)
            return

        # 0. Enter housing environment — stand ON a HOUSE tile on any surface map
        if (
            current_map_obj.tileset == "overland"
            and current_map_obj.get_tile(p_row, p_col) == HOUSE
        ):
            self._enter_housing(player, p_col, p_row)
            return

        # 0.5 / 0.6 / 0.7  — interactions inside a housing environment
        if self._is_in_housing_env(player):
            tile_id = current_map_obj.get_tile(p_row, p_col)

            # 0.7. Exit housing env
            if tile_id == HOUSE_EXIT:
                self._exit_housing(player)
                return

            # 0.6. Enter a sub-house (SETTLEMENT_HOUSE tile)
            if tile_id == SETTLEMENT_HOUSE:
                self._enter_sub_house(player, p_col, p_row)
                return

            # 0.5. Craft at worktable — standing on or adjacent to WORKTABLE
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                if current_map_obj.get_tile(p_row + dr, p_col + dc) == WORKTABLE:
                    self.craft_menus[pid] = 0
                    return

        # 1. Cave entry — standing on a cave entrance tile on a surface map
        if current_map_obj.tileset == "overland" and not (
            isinstance(player.current_map, tuple) and len(player.current_map) == 2
        ):
            tile_id = current_map_obj.get_tile(p_row, p_col)
            if tile_id in (CAVE_MOUNTAIN, CAVE_HILL):
                cave_key = (p_col, p_row)
                if cave_key not in self.maps:
                    surface_biome = getattr(
                        current_map_obj, "biome", BiomeType.STANDARD
                    )
                    env = CaveEnvironment(
                        p_col, p_row, cave_type=tile_id, biome=surface_biome
                    )
                    self.maps[cave_key] = MapScene(env.generate())
                cave_map = self.maps[cave_key]
                cave_map.origin_map = player.current_map
                player.x = cave_map.spawn_col * TILE + TILE // 2
                player.y = cave_map.spawn_row * TILE + TILE // 2
                player.current_map = cave_key
                self._snap_camera_to_player(player)
                self.floats.append(
                    FloatingText(
                        player.x,
                        player.y - 30,
                        "Entered cave!",
                        (100, 150, 255),
                        player.current_map,
                    )
                )
                return

        # 2. Cave exit — in a cave and standing on the exit tile
        if (
            isinstance(player.current_map, tuple)
            and len(player.current_map) == 2
            and hasattr(current_map_obj, "entrance_col")
        ):
            tile_id = current_map_obj.get_tile(p_row, p_col)
            if tile_id == CAVE_EXIT:
                origin_key = getattr(current_map_obj, "origin_map", "overland")
                origin_map = self.maps.get(origin_key)
                if origin_map is None:
                    origin_key = "overland"
                    origin_map = self.maps["overland"]
                entrance_col = current_map_obj.entrance_col
                entrance_row = current_map_obj.entrance_row
                placed = False
                for dr, dc in [
                    (1, 0),
                    (-1, 0),
                    (0, 1),
                    (0, -1),
                    (1, 1),
                    (-1, -1),
                    (1, -1),
                    (-1, 1),
                ]:
                    adj_c = entrance_col + dc
                    adj_r = entrance_row + dr
                    if 0 <= adj_c < origin_map.cols and 0 <= adj_r < origin_map.rows:
                        adj_tile = origin_map.get_tile(adj_r, adj_c)
                        if adj_tile not in (WATER, MOUNTAIN, CAVE_MOUNTAIN, CAVE_HILL):
                            player.x = adj_c * TILE + TILE // 2
                            player.y = adj_r * TILE + TILE // 2
                            placed = True
                            break
                if not placed:
                    player.x = entrance_col * TILE + TILE // 2
                    player.y = entrance_row * TILE + TILE // 2
                player.current_map = origin_key
                if player.on_mount:
                    self._dismount_player(player)
                self._snap_camera_to_player(player)
                self.floats.append(
                    FloatingText(
                        player.x,
                        player.y - 30,
                        "Exited cave!",
                        (100, 255, 150),
                        player.current_map,
                    )
                )
                return

        # 2.5. Underwater exit — standing on DIVE_EXIT returns player to the surface
        if (
            isinstance(player.current_map, tuple)
            and len(player.current_map) == 3
            and player.current_map[0] == "underwater"
        ):
            tile_id = current_map_obj.get_tile(p_row, p_col)
            if tile_id == DIVE_EXIT:
                origin_key = getattr(current_map_obj, "origin_map", "overland")
                origin_map = self.maps.get(origin_key)
                if origin_map is None:
                    origin_key = "overland"
                    origin_map = self.maps["overland"]
                # Place player back on the boat tile position
                dive_col = getattr(current_map_obj, "dive_col", 0)
                dive_row = getattr(current_map_obj, "dive_row", 0)
                player.x = dive_col * TILE + TILE // 2
                player.y = dive_row * TILE + TILE // 2
                player.current_map = origin_key
                # Restore boat at dive position (player is back on the water)
                player.on_boat = True
                player.boat_col = dive_col
                player.boat_row = dive_row
                origin_map.set_tile(dive_row, dive_col, WATER)
                if player.on_mount:
                    self._dismount_player(player)
                self._snap_camera_to_player(player)
                self.floats.append(
                    FloatingText(
                        player.x,
                        player.y - 30,
                        "Surfaced!",
                        (60, 200, 255),
                        player.current_map,
                    )
                )
                return

        # 3. On boat — dive if player has Scuba Gear, otherwise show sailing hint
        if player.on_boat:
            if player.inventory.get("Scuba Gear", 0) > 0:
                self._try_dive(player)
                return
            self.floats.append(
                FloatingText(
                    int(player.x),
                    int(player.y) - 36,
                    "Sail to the edge of the map!",
                    (100, 200, 255),
                    player.current_map,
                )
            )
            return

        # 3.5. Mount / dismount a nearby rideable creature
        if player.on_mount:
            self._dismount_player(player)
            self.floats.append(
                FloatingText(
                    int(player.x), int(player.y) - 30,
                    "Dismounted!", (180, 220, 100), player.current_map,
                )
            )
            return
        # Check for a nearby unmounted creature on the same map
        mount_range = TILE * 1.5
        player_scene = self.maps.get(player.current_map)
        for c in (player_scene.creatures if player_scene is not None else []):
            if c.rider_id is not None:
                continue
            dist = math.hypot(c.x - player.x, c.y - player.y)
            if dist <= mount_range:
                self._mount_player(player, c)
                self.floats.append(
                    FloatingText(
                        int(player.x), int(player.y) - 30,
                        "Mounted!", (100, 220, 180), player.current_map,
                    )
                )
                return

        # 4. Adjacent treasure chest
        for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
            cc, rr = p_col + dc, p_row + dr
            if current_map_obj.get_tile(rr, cc) == TREASURE_CHEST:
                current_map_obj.set_tile(rr, cc, GRASS)
                current_map_obj.set_tile_hp(rr, cc, 0)
                tx = cc * TILE + TILE // 2
                ty = rr * TILE + TILE // 2
                self._open_treasure_chest(player, tx, ty)
                return

        # 4.4 Adjacent SIGN — read its text
        if current_map_obj.tileset == "overland":
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == SIGN:
                    raw = object.__getattribute__(current_map_obj, "map")
                    text = raw.sign_texts.get((cc, rr), "...")
                    self._sign_display[pid] = {"text": text, "timer": 6.0}
                    return

        # 4.45 Adjacent BROKEN_LADDER — repair if player has materials
        if current_map_obj.tileset == "overland":
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == BROKEN_LADDER:
                    tx = cc * TILE + TILE // 2
                    ty = rr * TILE + TILE // 2
                    if all(
                        player.inventory.get(item, 0) >= qty
                        for item, qty in self._SKY_LADDER_COST.items()
                    ):
                        for item, qty in self._SKY_LADDER_COST.items():
                            player.inventory[item] -= qty
                        current_map_obj.set_tile(rr, cc, SKY_LADDER)
                        raw = object.__getattribute__(current_map_obj, "map")
                        raw.ladder_repaired = True
                        self.floats.append(FloatingText(
                            tx, ty - 36,
                            "Ladder repaired!", (120, 220, 80),
                            player.current_map,
                        ))
                        for _ in range(14):
                            self.particles.append(Particle(tx, ty, (200, 180, 80), player.current_map))
                    else:
                        needs = ", ".join(
                            f"{qty} {item}" for item, qty in self._SKY_LADDER_COST.items()
                        )
                        self.floats.append(FloatingText(
                            tx, ty - 30,
                            f"Need: {needs}", (255, 120, 80),
                            player.current_map,
                        ))
                    return

        # 4.46 Adjacent SKY_LADDER — ascend to sky view
        if current_map_obj.tileset == "overland":
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == SKY_LADDER:
                    self._enter_sky_view(player)
                    return

        # 4.5. Adjacent ANCIENT_STONE — ritual quest progress (surface maps only)
        if current_map_obj.tileset == "overland":
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == ANCIENT_STONE:
                    self._try_activate_ritual_stone(player, current_map_obj, cc, rr)
                    return

        # 4.6. Adjacent PORTAL_RUINS — show quest status or gather delivery
        if current_map_obj.tileset == "overland":
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == PORTAL_RUINS:
                    self._try_interact_portal_ruins(player, player.current_map)
                    return

        # 4.7. Adjacent PORTAL_ACTIVE on island — enter portal realm
        if current_map_obj.tileset == "overland":
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == PORTAL_ACTIVE:
                    self._enter_portal_realm(player)
                    return

        # 4.8. PORTAL_ACTIVE tile inside portal realm — exit to linked island
        if player.current_map == "portal_realm":
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == PORTAL_ACTIVE:
                    self._exit_portal_realm(player, cc, rr)
                    return

        # 5. On a PIER tile → try to build a boat in the next water cell
        if current_map_obj.get_tile(p_row, p_col) == PIER:
            for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == WATER:
                    cost = {"Wood": BOAT_BUILD_COST, "Sail": 1}
                    tx = p_col * TILE + TILE // 2
                    ty = p_row * TILE + TILE // 2
                    if not try_spend(player.inventory, cost):
                        self.floats.append(
                            FloatingText(
                                tx,
                                ty - 20,
                                f"Need {BOAT_BUILD_COST} Wood + 1 Sail!",
                                (255, 100, 100),
                                player.current_map,
                            )
                        )
                        return
                    current_map_obj.set_tile(rr, cc, BOAT)
                    current_map_obj.set_tile_hp(rr, cc, 0)
                    btx = cc * TILE + TILE // 2
                    bty = rr * TILE + TILE // 2
                    self.floats.append(
                        FloatingText(
                            btx,
                            bty - 20,
                            "Boat built!",
                            (100, 200, 255),
                            player.current_map,
                        )
                    )
                    for _ in range(12):
                        self.particles.append(
                            Particle(btx, bty, (80, 160, 220), player.current_map)
                        )
                    return

    # -- mount helpers -------------------------------------------------------

    def _mount_player(self, player: Player, creature: Creature) -> None:
        """Mount *player* onto *creature*.  Creature must be un-ridden."""
        creature.rider_id = player.player_id
        player.on_mount = True
        self._player_mounts[player.player_id] = creature

    def _dismount_player(self, player: Player) -> None:
        """Dismount *player* from their current creature.

        Snaps the player's position to the creature's position so the player
        appears at the creature's location after dismounting.
        """
        mount = self._player_mounts.get(player.player_id)
        if mount is not None:
            player.x = mount.x
            player.y = mount.y
            mount.rider_id = None
        player.on_mount = False
        self._player_mounts[player.player_id] = None

    def _try_dive(self, player: Player) -> None:
        """Transition from the boat surface into an underwater map at the current position."""
        dive_col = player.boat_col
        dive_row = player.boat_row
        if dive_col is None or dive_row is None:
            return

        dive_key = ("underwater", dive_col, dive_row)
        if dive_key not in self.maps:
            env = UnderwaterEnvironment(dive_col, dive_row)
            underwater_map = env.generate()
            underwater_map.origin_map = player.current_map
            dive_scene = MapScene(underwater_map)
            self.maps[dive_key] = dive_scene
            # Spawn sea creatures into this scene
            dive_scene.creatures.extend(env.spawn_creatures(underwater_map))
        else:
            underwater_map = self.maps[dive_key]
            underwater_map.origin_map = player.current_map

        player.on_boat = False
        player.x = underwater_map.spawn_col * TILE + TILE // 2
        player.y = underwater_map.spawn_row * TILE + TILE // 2
        player.current_map = dive_key
        self._snap_camera_to_player(player)
        self.floats.append(
            FloatingText(
                player.x, player.y - 30, "Diving!", (60, 200, 255), player.current_map
            )
        )
        for _ in range(12):
            self.particles.append(
                Particle(
                    int(player.x), int(player.y), (40, 160, 220), player.current_map
                )
            )

    def _try_activate_ritual_stone(
        self,
        player: Player,
        game_map: "GameMap",
        stone_col: int,
        stone_row: int,
    ) -> None:
        """Handle a player interacting with an ANCIENT_STONE ritual tile."""
        map_key = player.current_map
        quest = self.portal_quests.get(map_key)
        if (
            quest is None
            or quest["type"] != PortalQuestType.RITUAL
            or quest["restored"]
        ):
            return

        positions: list[tuple[int, int]] = getattr(
            game_map, "ritual_stone_positions", []
        )
        if not positions:
            return

        next_idx = quest["stones_activated"]
        if next_idx >= len(positions):
            return

        expected_col, expected_row = positions[next_idx]
        tx = stone_col * TILE + TILE // 2
        ty = stone_row * TILE + TILE // 2

        if (stone_col, stone_row) == (expected_col, expected_row):
            quest["stones_activated"] += 1
            remaining = quest["stones_total"] - quest["stones_activated"]
            self.floats.append(
                FloatingText(
                    tx, ty - 30, "Stone awakened!", (200, 180, 50), player.current_map
                )
            )
            for _ in range(10):
                self.particles.append(
                    Particle(tx, ty, (200, 180, 50), player.current_map)
                )
            if remaining == 0:
                if self._check_portal_restored(map_key):
                    self._announce_portal_restored(player)
        else:
            self.floats.append(
                FloatingText(
                    tx,
                    ty - 30,
                    "Not the next stone!",
                    (255, 100, 100),
                    player.current_map,
                )
            )

    def _try_interact_portal_ruins(self, player: Player, map_key: str | tuple) -> None:
        """Handle a player interacting with a PORTAL_RUINS tile."""
        quest = self.portal_quests.get(map_key)
        tx = int(player.x)
        ty = int(player.y) - 36

        if quest is None:
            self.floats.append(
                FloatingText(
                    tx, ty, "Ancient portal...", (180, 160, 200), player.current_map
                )
            )
            return

        if quest["restored"]:
            self.floats.append(
                FloatingText(
                    tx, ty, "Portal is active!", (160, 60, 220), player.current_map
                )
            )
            return

        if quest["type"] == PortalQuestType.RITUAL:
            done = quest["stones_activated"]
            total = quest["stones_total"]
            self.floats.append(
                FloatingText(
                    tx,
                    ty,
                    f"Ritual: {done}/{total} stones",
                    (200, 180, 50),
                    player.current_map,
                )
            )

        elif quest["type"] == PortalQuestType.GATHER:
            required = quest["required"]
            # Try to spend items if the player has enough
            can_afford = all(
                player.inventory.get(k, 0) >= v for k, v in required.items()
            )
            if can_afford:
                from src.world import try_spend as _try_spend

                if _try_spend(player.inventory, required):
                    if self._check_portal_restored(map_key):
                        self._announce_portal_restored(player)
            else:
                parts = ", ".join(f"{v} {k}" for k, v in required.items())
                self.floats.append(
                    FloatingText(
                        tx, ty, f"Need: {parts}", (255, 160, 80), player.current_map
                    )
                )

        elif quest["type"] == PortalQuestType.COMBAT:
            if quest.get("guardian_defeated"):
                if self._check_portal_restored(map_key):
                    self._announce_portal_restored(player)
            else:
                self.floats.append(
                    FloatingText(
                        tx,
                        ty,
                        "A guardian blocks the portal!",
                        (200, 80, 80),
                        player.current_map,
                    )
                )

    def _announce_portal_restored(self, player: Player) -> None:
        """Show a restoration announcement floating text."""
        self.floats.append(
            FloatingText(
                int(player.x),
                int(player.y) - 50,
                "Portal restored!",
                (160, 60, 220),
                player.current_map,
            )
        )
        for _ in range(20):
            self.particles.append(
                Particle(
                    int(player.x), int(player.y), (160, 60, 220), player.current_map
                )
            )
        # Register this island's portal in the realm (no-op if realm not yet generated)
        self._add_realm_portal(player.current_map)

    def _get_sector_coords(self, map_key: str | tuple) -> tuple[int, int] | None:
        """Return (sx, sy) sector coordinates for a surface map key, or None."""
        if map_key == "overland":
            return (0, 0)
        if isinstance(map_key, tuple) and len(map_key) == 3 and map_key[0] == "sector":
            return (map_key[1], map_key[2])
        return None

    def _expand_realm(
        self,
        realm_map: "GameMap",
        left: int,
        right: int,
        top: int,
        bottom: int,
    ) -> None:
        """Grow the realm's world array by the given number of slots in each direction.

        New areas are filled with PORTAL_WALL.  All positional attrs on realm_map
        (spawn_col/row, portal_exits coords, origin_sx/sy) are shifted accordingly.
        """
        slot_size = realm_map.slot_size
        add_left = left * slot_size
        add_right = right * slot_size  # noqa: F841
        add_top = top * slot_size
        add_bottom = bottom * slot_size  # noqa: F841
        old_rows = realm_map.rows
        old_cols = realm_map.cols
        new_rows = old_rows + add_top + bottom * slot_size
        new_cols = old_cols + add_left + right * slot_size

        world = [[PORTAL_WALL] * new_cols for _ in range(new_rows)]
        tile_hp = [[0] * new_cols for _ in range(new_rows)]
        for r in range(old_rows):
            for c in range(old_cols):
                world[r + add_top][c + add_left] = realm_map.world[r][c]
                tile_hp[r + add_top][c + add_left] = realm_map.tile_hp[r][c]

        realm_map.world = world
        realm_map.tile_hp = tile_hp
        realm_map.rows = new_rows
        realm_map.cols = new_cols
        realm_map.origin_sx -= left
        realm_map.origin_sy -= top
        realm_map.spawn_col += add_left
        realm_map.spawn_row += add_top
        # Track the number of slots (cols/rows // slot_size gives wrong answer with padding)
        if hasattr(realm_map, "slot_cols"):
            realm_map.slot_cols += left + right
        if hasattr(realm_map, "slot_rows"):
            realm_map.slot_rows += top + bottom
        # Shift all existing portal exit positions to match the new coordinate space
        new_exits: dict = {}
        for (col, row), mk in realm_map.portal_exits.items():
            new_exits[(col + add_left, row + add_top)] = mk
        realm_map.portal_exits = new_exits

    def _ensure_realm_slot(self, sx: int, sy: int) -> tuple[int, int]:
        """Ensure the realm has a carved chamber for sector (sx, sy).

        Expands the world array in-place if the sector falls outside the current
        bounds, then carves a 12×12 chamber and connects it via L-corridors.
        Returns (portal_col, portal_row) — the centre of the chamber.
        """
        from src.world.environments.portal_realm import carve_chamber
        from src.world.environments.utils import connect_regions
        from src.config import PORTAL_FLOOR, TREASURE_CHEST, PORTAL_ACTIVE

        realm_map = self.maps["portal_realm"]
        slot_size = realm_map.slot_size
        slot_pad = getattr(realm_map, "slot_padding", 0)
        origin_sx = realm_map.origin_sx
        origin_sy = realm_map.origin_sy
        # Number of slots in each dimension (may be tracked explicitly if padding present)
        if hasattr(realm_map, "slot_cols"):
            cur_s_cols = realm_map.slot_cols
            cur_s_rows = realm_map.slot_rows
        else:
            cur_s_cols = realm_map.cols // slot_size
            cur_s_rows = realm_map.rows // slot_size

        expand_left = max(0, origin_sx - sx)
        expand_right = max(0, sx - (origin_sx + cur_s_cols - 1))
        expand_top = max(0, origin_sy - sy)
        expand_bottom = max(0, sy - (origin_sy + cur_s_rows - 1))

        if expand_left or expand_right or expand_top or expand_bottom:
            self._expand_realm(
                realm_map, expand_left, expand_right, expand_top, expand_bottom
            )
            origin_sx = realm_map.origin_sx
            origin_sy = realm_map.origin_sy

        ix = sx - origin_sx
        iy = sy - origin_sy
        slot_col = slot_pad + ix * slot_size
        slot_row = slot_pad + iy * slot_size

        carve_chamber(realm_map.world, slot_col, slot_row)
        connect_regions(
            realm_map.world,
            realm_map.rows,
            realm_map.cols,
            realm_map.spawn_col,
            realm_map.spawn_row,
            {PORTAL_FLOOR, TREASURE_CHEST, PORTAL_ACTIVE},
            PORTAL_FLOOR,
            getattr(realm_map, "slot_padding", 2),
        )

        portal_col = slot_col + slot_size // 2
        portal_row = slot_row + slot_size // 2
        return portal_col, portal_row

    def _add_realm_chest_near(
        self, realm_map: "GameMap", portal_col: int, portal_row: int
    ) -> None:
        """Place a TREASURE_CHEST on the nearest free PORTAL_FLOOR tile to the portal."""
        for dc, dr in [
            (1, 0),
            (-1, 0),
            (0, 1),
            (0, -1),
            (2, 0),
            (-2, 0),
            (0, 2),
            (0, -2),
        ]:
            c, r = portal_col + dc, portal_row + dr
            if realm_map.get_tile(r, c) == PORTAL_FLOOR:
                realm_map.world[r][c] = TREASURE_CHEST
                return

    def _add_realm_portal(self, dest_map_key: str | tuple) -> None:
        """Place a PORTAL_ACTIVE tile in the portal realm linking to dest_map_key.

        No-op if the realm has not been generated yet, if dest_map_key is not a
        surface island, or if it is already registered.
        """
        if "portal_realm" not in self.maps:
            return
        coords = self._get_sector_coords(dest_map_key)
        if coords is None:
            return

        realm_map = self.maps["portal_realm"]
        if not hasattr(realm_map, "portal_exits"):
            realm_map.portal_exits = {}
        if not hasattr(realm_map, "slot_size"):
            return  # old-format realm from save — will be regenerated on entry
        if dest_map_key in realm_map.portal_exits.values():
            return  # already registered

        sx, sy = coords
        portal_col, portal_row = self._ensure_realm_slot(sx, sy)
        realm_map.world[portal_row][portal_col] = PORTAL_ACTIVE
        realm_map.portal_exits[(portal_col, portal_row)] = dest_map_key

        # Spawn a chest in the same slot, offset from the portal tile
        self._add_realm_chest_near(realm_map, portal_col, portal_row)

    # ------------------------------------------------------------------
    # Housing environment transitions
    # ------------------------------------------------------------------

    def _is_in_housing_env(self, player: Player) -> bool:
        """Return True when the player is inside any housing environment."""
        key = player.current_map
        return (
            isinstance(key, tuple)
            and len(key) >= 3
            and key[0] in ("house", "house_sub")
        )

    def _enter_housing(self, player: Player, entry_col: int, entry_row: int) -> None:
        """Generate (or retrieve) the housing env for the given HOUSE tile and enter it."""
        house_key = ("house", entry_col, entry_row)
        if house_key not in self.maps:
            current_map_obj = self.get_player_current_map(player)
            cluster_size = (
                current_map_obj.town_clusters.get((entry_row, entry_col), 1)
                if current_map_obj is not None
                else 1
            )
            tier, tier_name = self._get_settlement_tier(cluster_size)
            exterior_tile = self._sample_exterior_tile(
                current_map_obj, entry_col, entry_row
            )
            env = HousingEnvironment(
                entry_col, entry_row, tier, exterior_tile=exterior_tile
            )
            house_map = env.generate()
            house_map.housing_tier = tier
            house_map.entrance_col = entry_col
            house_map.entrance_row = entry_row
            house_map.origin_map = player.current_map
            self.maps[house_key] = MapScene(house_map)
        else:
            house_map = self.maps[house_key]
            # Always refresh origin_map so re-entering from a different sector works
            house_map.origin_map = player.current_map

        tier_name = SETTLEMENT_TIER_NAMES[getattr(house_map, "housing_tier", 0)]
        player.x = house_map.spawn_col * TILE + TILE // 2
        player.y = house_map.spawn_row * TILE + TILE // 2
        player.current_map = house_key
        self._snap_camera_to_player(player)
        self.floats.append(
            FloatingText(
                player.x,
                player.y - 30,
                f"Entered {tier_name}!",
                (255, 200, 120),
                player.current_map,
            )
        )

    @staticmethod
    def _sample_exterior_tile(game_map: "GameMap | None", col: int, row: int) -> int:
        """Sample the overland tiles around (col, row) to pick a housing exterior tile.

        Considers GRASS, DIRT, and TREE tiles in a 5×5 window and returns the
        most common one.  Falls back to GRASS if nothing suitable is found.
        """
        if game_map is None:
            return GRASS
        _CANDIDATES = {GRASS, DIRT, TREE}
        counts: dict[int, int] = {}
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                if dr == 0 and dc == 0:
                    continue
                r, c = row + dr, col + dc
                if 0 <= r < game_map.rows and 0 <= c < game_map.cols:
                    t = game_map.get_tile(r, c)
                    if t in _CANDIDATES:
                        counts[t] = counts.get(t, 0) + 1
        return max(counts, key=lambda k: counts[k]) if counts else GRASS

    def _enter_sub_house(self, player: Player, sh_col: int, sh_row: int) -> None:
        """Enter one of the SETTLEMENT_HOUSE tiles within a settlement environment."""
        parent_key = player.current_map
        # Look up this sub-house in the parent map's sub_house_positions list.
        # Entries are (col, row, interior_w, interior_h); old saves may be (col, row).
        parent_map = self.get_player_current_map(player)
        positions: list[tuple] = getattr(parent_map, "sub_house_positions", [])
        sub_idx = next(
            (i for i, e in enumerate(positions) if e[0] == sh_col and e[1] == sh_row),
            sh_col * 1000 + sh_row,  # fallback unique id if not found
        )
        entry = (
            positions[sub_idx]
            if isinstance(sub_idx, int) and sub_idx < len(positions)
            else None
        )
        iw = int(entry[2]) if entry is not None and len(entry) >= 4 else 3
        ih = int(entry[3]) if entry is not None and len(entry) >= 4 else 3

        sub_key: tuple = ("house_sub", sh_col, sh_row, sub_idx)
        if sub_key not in self.maps:
            # Generate a variable-sized interior matching the exterior footprint
            sub_seed_col = sh_col + (sub_idx if isinstance(sub_idx, int) else 0) * 37
            sub_seed_row = sh_row + (sub_idx if isinstance(sub_idx, int) else 0) * 53
            env = HousingEnvironment(
                sub_seed_col, sub_seed_row, tier=0, sub_w=iw, sub_h=ih
            )
            sub_map = env.generate()
            sub_map.housing_tier = 0
            sub_map.entrance_col = sh_col
            sub_map.entrance_row = sh_row
            sub_map.origin_map = parent_key
            self.maps[sub_key] = MapScene(sub_map)
        else:
            sub_map = self.maps[sub_key]
            sub_map.origin_map = parent_key

        player.x = sub_map.spawn_col * TILE + TILE // 2
        player.y = sub_map.spawn_row * TILE + TILE // 2
        player.current_map = sub_key
        self._snap_camera_to_player(player)
        self.floats.append(
            FloatingText(
                player.x,
                player.y - 30,
                "Entered house!",
                (255, 200, 120),
                player.current_map,
            )
        )

    def _exit_housing(self, player: Player) -> None:
        """Exit the current housing environment and return to origin map."""
        current_map_obj = self.get_player_current_map(player)
        if current_map_obj is None:
            return

        origin_key = getattr(current_map_obj, "origin_map", "overland")
        origin_map = self.maps.get(origin_key)
        if origin_map is None:
            origin_key = "overland"
            origin_map = self.maps["overland"]

        entrance_col = getattr(current_map_obj, "entrance_col", 0)
        entrance_row = getattr(current_map_obj, "entrance_row", 0)

        # If returning to another housing env, land on the SETTLEMENT_HOUSE tile
        if isinstance(origin_key, tuple) and origin_key[0] in ("house", "house_sub"):
            player.x = entrance_col * TILE + TILE // 2
            player.y = entrance_row * TILE + TILE // 2
        else:
            # Returning to overland/sector — find a walkable tile near the entrance
            placed = False
            for dr, dc in [
                (1, 0),
                (-1, 0),
                (0, 1),
                (0, -1),
                (1, 1),
                (-1, -1),
                (1, -1),
                (-1, 1),
            ]:
                adj_c = entrance_col + dc
                adj_r = entrance_row + dr
                if 0 <= adj_c < origin_map.cols and 0 <= adj_r < origin_map.rows:
                    adj_tile = origin_map.get_tile(adj_r, adj_c)
                    if adj_tile not in (WATER, MOUNTAIN, CAVE_MOUNTAIN, CAVE_HILL):
                        player.x = adj_c * TILE + TILE // 2
                        player.y = adj_r * TILE + TILE // 2
                        placed = True
                        break
            if not placed:
                player.x = entrance_col * TILE + TILE // 2
                player.y = entrance_row * TILE + TILE // 2

        player.current_map = origin_key
        self._snap_camera_to_player(player)
        self.floats.append(
            FloatingText(
                player.x,
                player.y - 30,
                "Exited house!",
                (200, 255, 200),
                player.current_map,
            )
        )

    def _enter_portal_realm(self, player: Player) -> None:
        """Teleport the player into the portal realm, spawning at their origin portal."""
        origin_key = player.current_map

        # Regenerate if the saved realm lacks the slot-grid attrs (old save compat)
        if "portal_realm" in self.maps:
            rm = self.maps["portal_realm"]
            if not hasattr(rm, "slot_size") or not hasattr(rm, "origin_sx"):
                del self.maps["portal_realm"]

        if "portal_realm" not in self.maps:
            env = PortalRealmEnvironment()
            self.maps["portal_realm"] = MapScene(env.generate())
            # Backfill portals for every already-restored island
            for mk, quest in self.portal_quests.items():
                if quest.get("restored"):
                    self._add_realm_portal(mk)

        # Ensure origin island has a portal carved (also handles F9 debug first entry)
        self._add_realm_portal(origin_key)

        realm_map = self.maps["portal_realm"]
        player.portal_origin_map = origin_key
        player.current_map = "portal_realm"

        # Spawn at the origin island's portal tile in the realm
        origin_portal = next(
            (
                (c, r)
                for (c, r), mk in realm_map.portal_exits.items()
                if mk == origin_key
            ),
            None,
        )
        if origin_portal is not None:
            player.x = origin_portal[0] * TILE + TILE // 2
            player.y = origin_portal[1] * TILE + TILE // 2
        else:
            player.x = realm_map.spawn_col * TILE + TILE // 2
            player.y = realm_map.spawn_row * TILE + TILE // 2

        self._snap_camera_to_player(player)
        self.portal_warp[player.player_id] = {"progress": 0.0}
        self.floats.append(
            FloatingText(
                int(player.x),
                int(player.y) - 30,
                "Entered portal realm!",
                (160, 60, 220),
                player.current_map,
            )
        )

    def _exit_portal_realm(
        self,
        player: Player,
        portal_col: int | None = None,
        portal_row: int | None = None,
    ) -> None:
        """Return the player from the portal realm.

        If portal_col/row are given, look up the destination in the realm's
        portal_exits dict so each portal leads to a specific island.  Falls
        back to portal_origin_map when the tile is unknown.
        """
        realm_map = self.maps.get("portal_realm")
        dest_key: str | tuple | None = None
        if (
            realm_map is not None
            and portal_col is not None
            and hasattr(realm_map, "portal_exits")
        ):
            dest_key = realm_map.portal_exits.get((portal_col, portal_row))

        if dest_key is None:
            dest_key = player.portal_origin_map or "overland"

        dest_map = self.maps.get(dest_key)
        if dest_map is None:
            dest_key = "overland"
            dest_map = self.maps["overland"]

        # Place near the portal on the destination island
        p_col = getattr(dest_map, "portal_col", dest_map.cols // 2)
        p_row = getattr(dest_map, "portal_row", dest_map.rows // 2)
        placed = False
        for dr, dc in [
            (1, 0),
            (-1, 0),
            (0, 1),
            (0, -1),
            (2, 0),
            (-2, 0),
            (0, 2),
            (0, -2),
        ]:
            adj_c = p_col + dc
            adj_r = p_row + dr
            if 0 <= adj_c < dest_map.cols and 0 <= adj_r < dest_map.rows:
                if dest_map.get_tile(adj_r, adj_c) == GRASS:
                    player.x = adj_c * TILE + TILE // 2
                    player.y = adj_r * TILE + TILE // 2
                    placed = True
                    break
        if not placed:
            player.x = p_col * TILE + TILE // 2
            player.y = p_row * TILE + TILE // 2

        player.current_map = dest_key
        player.portal_origin_map = None
        # Record this exit as the respawn anchor
        player.last_portal_exit_map = dest_key
        player.last_portal_exit_x = player.x
        player.last_portal_exit_y = player.y
        self._snap_camera_to_player(player)
        self.portal_warp[player.player_id] = {"progress": 0.0}
        self.floats.append(
            FloatingText(
                int(player.x),
                int(player.y) - 30,
                "Left portal realm!",
                (180, 160, 220),
                player.current_map,
            )
        )

    def _debug_spawn_houses(self, player: Player) -> None:
        """DEBUG (F8): Spawn one cluster for each housing tier near player 1.

        Tiers and cluster sizes (tiles wide × tall):
          Cottage    (1):  1×1
          Hamlet     (2):  1×2
          Village    (4):  2×2
          Town       (9):  3×3
          Large Town (16): 4×4
          City       (25): 5×5

        Only works on overland maps.  Mineable tiles inside chosen regions
        are cleared to GRASS first.  Impassable non-mineable tiles (water,
        mountain) still block placement.
        """
        current_map = self.maps.get(player.current_map)
        if current_map is None or current_map.tileset != "overland":
            self.floats.append(
                FloatingText(
                    int(player.x),
                    int(player.y) - 30,
                    "[DEBUG] Must be on overland!",
                    (255, 100, 100),
                    player.current_map,
                )
            )
            return

        origin_col = int(player.x) // TILE
        origin_row = int(player.y) // TILE

        def _tile_clearable(tile_id: int) -> bool:
            if tile_id == GRASS:
                return True
            return bool(TILE_INFO.get(tile_id, {}).get("mineable", False))

        def _find_clearable_region(
            need_cols: int, need_rows: int, skip: set[tuple[int, int]]
        ) -> tuple[int, int] | None:
            for radius in range(2, 60):
                for dr in range(-radius, radius + 1):
                    for dc in range(-radius, radius + 1):
                        if abs(dr) != radius and abs(dc) != radius:
                            continue
                        top_r = origin_row + dr
                        left_c = origin_col + dc
                        fits = True
                        for rr in range(top_r, top_r + need_rows):
                            for cc in range(left_c, left_c + need_cols):
                                if not (
                                    0 <= rr < current_map.rows
                                    and 0 <= cc < current_map.cols
                                ):
                                    fits = False
                                    break
                                if (cc, rr) in skip:
                                    fits = False
                                    break
                                if not _tile_clearable(current_map.get_tile(rr, cc)):
                                    fits = False
                                    break
                            if not fits:
                                break
                        if fits:
                            return (left_c, top_r)
            return None

        def _clear_and_place(left_c: int, top_r: int, w: int, h: int) -> None:
            for rr in range(top_r, top_r + h):
                for cc in range(left_c, left_c + w):
                    current_map.set_tile(rr, cc, GRASS)
                    current_map.set_tile_hp(rr, cc, 0)
            for rr in range(top_r, top_r + h):
                for cc in range(left_c, left_c + w):
                    current_map.set_tile(rr, cc, HOUSE)
                    current_map.set_tile_hp(rr, cc, 0)

        # Cluster dimensions for each tier (w × h, all connected = correct tier)
        # SETTLEMENT_TIER_SIZES = [1, 2, 4, 9, 16, 25]
        clusters: list[tuple[int, int, str]] = [
            (1, 1, "Cottage"),
            (2, 1, "Hamlet"),
            (2, 2, "Village"),
            (3, 3, "Town"),
            (4, 4, "Large Town"),
            (5, 5, "City"),
        ]

        # Track all placed+buffer tiles to keep clusters separated by 1 tile gap
        occupied: set[tuple[int, int]] = set()
        placed_count = 0

        for w, h, name in clusters:
            pos = _find_clearable_region(w, h, occupied)
            if pos is None:
                self.floats.append(
                    FloatingText(
                        int(player.x),
                        int(player.y) - 30,
                        f"[DEBUG] No room for {name}!",
                        (255, 180, 100),
                        player.current_map,
                    )
                )
                continue

            left_c, top_r = pos
            _clear_and_place(left_c, top_r, w, h)
            self._update_town_clusters(left_c, top_r, player, current_map)
            placed_count += 1

            # Mark the region + 1-tile border as occupied for the next search
            for rr in range(top_r - 1, top_r + h + 1):
                for cc in range(left_c - 1, left_c + w + 1):
                    occupied.add((cc, rr))

        if placed_count:
            self.floats.append(
                FloatingText(
                    int(player.x),
                    int(player.y) - 52,
                    f"[DEBUG] {placed_count}/6 tier clusters spawned!",
                    (255, 200, 100),
                    player.current_map,
                )
            )

    def _debug_give_all_items(self) -> None:
        """DEBUG (F9): Give both players all equippable items and key materials."""
        from src.data.armor import ARMOR_PIECES, ACCESSORY_PIECES

        equippables = list(ARMOR_PIECES.keys()) + list(ACCESSORY_PIECES.keys())
        materials = {
            "Stone": 50,
            "Iron": 30,
            "Gold": 20,
            "Diamond": 30,
            "Wood": 30,
            "Dirt": 40,
            "Coral": 20,
            "Ancient Stone": 10,
            "Scuba Gear": 1,
        }

        for player in (self.player1, self.player2):
            for item in equippables:
                player.inventory[item] = player.inventory.get(item, 0) + 2
            for item, qty in materials.items():
                player.inventory[item] = player.inventory.get(item, 0) + qty

        self.floats.append(
            FloatingText(
                int(self.player1.x),
                int(self.player1.y) - 52,
                "[DEBUG] All items granted!",
                (100, 220, 255),
                self.player1.current_map,
            )
        )

    def _debug_restore_portal(self, player: Player) -> None:
        """DEBUG (F9): Force-restore the portal on the island player is currently on."""
        map_key = player.current_map
        # Only works on surface maps (overland / sector islands)
        game_map = self.maps.get(map_key)
        if game_map is None or game_map.tileset not in ("overland",):
            self.floats.append(
                FloatingText(
                    int(player.x),
                    int(player.y) - 36,
                    "[DEBUG] No portal here",
                    (180, 80, 80),
                    player.current_map,
                )
            )
            return

        self._debug_force_portal_on_map(map_key, game_map)
        self._add_realm_portal(map_key)

        # Generate a nearby island and restore its portal too so the realm
        # has two portals and the player can traverse between them.
        origin_sx = (
            map_key[1] if isinstance(map_key, tuple) and len(map_key) == 3 else 0
        )
        origin_sy = (
            map_key[2] if isinstance(map_key, tuple) and len(map_key) == 3 else 0
        )
        self._debug_ensure_nearby_island(origin_sx, origin_sy)

        self.floats.append(
            FloatingText(
                int(player.x),
                int(player.y) - 36,
                "[DEBUG] Portal + nearby island ready!",
                (160, 60, 220),
                player.current_map,
            )
        )

    def _debug_force_portal_on_map(
        self, map_key: str | tuple, game_map: "GameMap"
    ) -> None:
        """Force-complete the portal quest for map_key and flip the tile."""
        if map_key not in self.portal_quests:
            self._assign_portal_quest(map_key)
            self._place_portal_on_map(game_map, map_key)

        quest = self.portal_quests[map_key]
        if quest["type"] == PortalQuestType.RITUAL:
            quest["stones_activated"] = quest["stones_total"]
        elif quest["type"] == PortalQuestType.COMBAT:
            quest["guardian_defeated"] = True
            quest["guardian_spawned"] = True

        quest["restored"] = False
        if quest["type"] == PortalQuestType.GATHER:
            quest["restored"] = True
            if hasattr(game_map, "portal_col"):
                game_map.set_tile(
                    game_map.portal_row, game_map.portal_col, PORTAL_ACTIVE
                )
        else:
            self._check_portal_restored(map_key)

    def _debug_ensure_nearby_island(self, origin_sx: int, origin_sy: int) -> None:
        """Expand outward from origin until TWO sectors with islands are found,
        generating them if needed, and force-restoring their portals."""
        found = 0
        for dist in range(1, 16):
            for dx in range(-dist, dist + 1):
                for dy in range(-dist, dist + 1):
                    if abs(dx) != dist and abs(dy) != dist:
                        continue
                    sx, sy = origin_sx + dx, origin_sy + dy
                    sector_map = self._get_or_generate_sector(sx, sy)
                    # Mark all intermediate sectors as visited so the minimap
                    # shows them rather than leaving gaps in the fog of war
                    self.visited_sectors.add((sx, sy))
                    if (sx, sy) not in self.land_sectors:
                        continue
                    sector_key = (
                        ("sector", sx, sy) if (sx, sy) != (0, 0) else "overland"
                    )
                    self._debug_force_portal_on_map(sector_key, sector_map)
                    self._add_realm_portal(sector_key)
                    found += 1
                    if found >= 2:
                        return

    def _on_sentinel_defeated(self, map_key: str | tuple) -> None:
        quest = self.portal_quests.get(map_key)
        if quest is None or quest["type"] != PortalQuestType.COMBAT:
            return
        quest["guardian_defeated"] = True
        if self._check_portal_restored(map_key):
            # Announce to any player on this map
            for player in (self.player1, self.player2):
                if player.current_map == map_key:
                    self._announce_portal_restored(player)
                    break

    def _try_build_pier(self, player: Player) -> None:
        if player.on_boat:
            return

        current_map_obj = self.get_player_current_map(player)
        if current_map_obj is None:
            return

        p_col = int(player.x) // TILE
        p_row = int(player.y) // TILE
        rows = current_map_obj.rows
        cols = current_map_obj.cols
        tx = p_col * TILE + TILE // 2
        ty = p_row * TILE + TILE // 2

        if current_map_obj.get_tile(p_row, p_col) not in (GRASS, DIRT):
            self.floats.append(
                FloatingText(
                    tx, ty - 20, "Build on land!", (255, 100, 100), player.current_map
                )
            )
            return

        if not try_spend(player.inventory, {"Wood": PIER_BUILD_COST}):
            self.floats.append(
                FloatingText(
                    tx,
                    ty - 20,
                    f"Need {PIER_BUILD_COST} Wood!",
                    (255, 100, 100),
                    player.current_map,
                )
            )
            return

        # Prefer facing direction; fall back to all four cardinal directions
        fdx = player.facing_dx
        fdy = player.facing_dy
        if abs(fdx) >= abs(fdy):
            pref = (1 if fdx > 0 else -1, 0)
        else:
            pref = (0, 1 if fdy > 0 else -1)
        all_dirs = [pref] + [d for d in [(1, 0), (-1, 0), (0, 1), (0, -1)] if d != pref]

        for dc, dr in all_dirs:
            c1, r1 = p_col + dc, p_row + dr
            c2, r2 = p_col + dc * 2, p_row + dr * 2
            if (
                0 <= c1 < cols
                and 0 <= r1 < rows
                and 0 <= c2 < cols
                and 0 <= r2 < rows
                and current_map_obj.get_tile(r1, c1) == WATER
                and current_map_obj.get_tile(r2, c2) == WATER
            ):
                current_map_obj.set_tile(r1, c1, PIER)
                current_map_obj.set_tile_hp(r1, c1, 0)
                current_map_obj.set_tile(r2, c2, PIER)
                current_map_obj.set_tile_hp(r2, c2, 0)
                self.floats.append(
                    FloatingText(
                        tx, ty - 20, "Pier built!", (200, 160, 60), player.current_map
                    )
                )
                return

        # Refund
        player.inventory["Wood"] = player.inventory.get("Wood", 0) + PIER_BUILD_COST
        self.floats.append(
            FloatingText(
                tx,
                ty - 20,
                "No water to build on!",
                (255, 100, 100),
                player.current_map,
            )
        )

    def _get_player_sector(self, player: Player) -> tuple[int, int] | None:
        """Return the (sx, sy) sector coordinates for a player's current map.

        Overland/"overland" maps map to sector (0, 0).
        Sector maps keyed as ("sector", sx, sy) return (sx, sy).
        Cave and housing maps return None (no sector transitions underground/indoors).
        """
        key = player.current_map
        if key == "overland" or key == ("sector", 0, 0):
            return (0, 0)
        if isinstance(key, tuple) and len(key) == 3 and key[0] == "sector":
            return (key[1], key[2])
        return None  # cave, housing, or unknown

    def _get_or_generate_sector(self, sx: int, sy: int) -> "MapScene":
        """Return (or lazily generate) the GameMap for sector (sx, sy)."""
        if sx == 0 and sy == 0:
            return self.maps["overland"]
        key = ("sector", sx, sy)
        if key not in self.maps:
            world_data, has_island, biome = generate_ocean_sector(
                sx, sy, self.world_seed
            )
            sector_map = GameMap(world_data, tileset="overland")
            sector_map.biome = biome
            sector_map.enemies = spawn_enemies(world_data, biome)
            sector_scene = MapScene(sector_map)
            self.maps[key] = sector_scene
            # Record if this sector has a full island (not just atolls)
            if has_island:
                self.land_sectors.add((sx, sy))
                # Assign and place portal quest for this island
                self._assign_portal_quest(key)
                self._place_portal_on_map(sector_map, key)
                # Spawn land creatures (horses) on standard-biome islands only
                if biome == BiomeType.STANDARD:
                    land_env = OverlandEnvironment(map_key=key)
                    sector_scene.creatures.extend(land_env.spawn_creatures(sector_map))
            # Restore any archived entities from before eviction
            archived = self._entity_archive.pop(key, None)
            if archived:
                from src.save import _deserialize_worker, _deserialize_pet, _deserialize_creature
                sector_scene.workers.extend(_deserialize_worker(w) for w in archived.get("workers", []))
                sector_scene.pets.extend(_deserialize_pet(p) for p in archived.get("pets", []))
                sector_scene.creatures.extend(_deserialize_creature(c) for c in archived.get("creatures", []))
        return self.maps[key]

    def _evict_distant_sectors(self) -> None:
        """Drop sector maps that are more than 2 sectors away from all players."""
        sectors_in_use = set()
        for player in (self.player1, self.player2):
            coords = self._get_player_sector(player)
            if coords is None:
                continue
            sx, sy = coords
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    sectors_in_use.add((sx + dx, sy + dy))

        to_evict = []
        for key in self.maps:
            if isinstance(key, tuple) and len(key) == 3 and key[0] == "sector":
                if key[1] != 0 or key[2] != 0:  # never evict home island
                    if (key[1], key[2]) not in sectors_in_use:
                        to_evict.append(key)
        for key in to_evict:
            scene = self.maps.get(key)
            if isinstance(scene, MapScene):
                # Archive entities before eviction so they survive sector reload
                from src.save import _serialize_worker, _serialize_pet, _serialize_creature
                self._entity_archive[key] = {
                    "workers": [_serialize_worker(w) for w in scene.workers],
                    "pets": [_serialize_pet(p) for p in scene.pets],
                    "creatures": [_serialize_creature(c) for c in scene.creatures],
                }
            del self.maps[key]

    def _check_biome_entry_armor(self, player: Player, biome: BiomeType) -> bool:
        """Return True if the player meets the armor requirement for the given biome."""
        body_slots = ["helmet", "chest", "legs", "boots"]
        if biome == BiomeType.TUNDRA:
            # Any armor equipped in any body slot
            return any(player.equipment.get(s) is not None for s in body_slots)
        if biome == BiomeType.VOLCANO:
            # Full armor set — all 4 body slots occupied
            return all(player.equipment.get(s) is not None for s in body_slots)
        return True

    def _has_ancient_armor(self, player: Player) -> bool:
        """Return True if the player has at least one Ancient material armor piece equipped."""
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

    def check_sector_transitions(self, player: Player) -> None:
        """Detect when an on-boat player crosses the edge of their current sector
        and teleport them to the adjacent sector with a brief wipe animation."""
        if not player.on_boat:
            return
        sector_coords = self._get_player_sector(player)
        if sector_coords is None:
            return  # underground — no sector transitions

        sx, sy = sector_coords
        current_map = self._get_or_generate_sector(sx, sy)
        world_pixel_w = current_map.cols * TILE
        world_pixel_h = current_map.rows * TILE

        x, y = player.x, player.y
        pid = player.player_id
        direction = None
        new_sx, new_sy = sx, sy
        new_x, new_y = x, y

        margin = TILE // 2  # cross within half a tile of the edge

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

        # Generate next sector (may be cached)
        self._get_or_generate_sector(new_sx, new_sy)

        # Move the player to the new sector
        new_key = (
            ("sector", new_sx, new_sy) if (new_sx != 0 or new_sy != 0) else "overland"
        )
        player.current_map = new_key
        player.x = new_x
        player.y = new_y
        self._snap_camera_to_player(player)

        # Record the new sector as visited
        self.visited_sectors.add((new_sx, new_sy))

        # Check biome entry armor requirement for island sectors
        if (new_sx, new_sy) in self.land_sectors and new_sx != 0 and new_sy != 0:
            from src.world.generation import get_sector_biome

            biome = get_sector_biome(self.world_seed, new_sx, new_sy)
            if not self._check_biome_entry_armor(player, biome):
                _BIOME_WARNINGS = {
                    BiomeType.TUNDRA: "Too cold! Equip armor!",
                    BiomeType.VOLCANO: "Too hot! Full armor set needed!",
                }
                msg = _BIOME_WARNINGS.get(biome)
                if msg:
                    self.floats.append(
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

        # Start the wipe animation (skip if player is on a boat)
        if not player.on_boat:
            self.sector_wipe[pid] = {
                "progress": 0.0,
                "direction": direction,
            }

        self._evict_distant_sectors()

    def _snap_camera_to_player(self, player: Player) -> None:
        """Immediately snap a player's camera to centre on that player."""
        if player.player_id == 1:
            self.cam1_x = player.x - self.viewport_w // 2
            self.cam1_y = player.y - self.viewport_h // 2
        else:
            self.cam2_x = player.x - self.viewport_w // 2
            self.cam2_y = player.y - self.viewport_h // 2

    @staticmethod
    def _get_settlement_tier(cluster_size: int) -> tuple[int, str]:
        """Return (tier_index, tier_name) for a given cluster size."""
        for i in range(len(SETTLEMENT_TIER_SIZES) - 1, -1, -1):
            if cluster_size >= SETTLEMENT_TIER_SIZES[i]:
                return (i, SETTLEMENT_TIER_NAMES[i])
        return (0, SETTLEMENT_TIER_NAMES[0])

    def _update_town_clusters(
        self,
        build_col: int,
        build_row: int,
        player: Player,
        game_map: "GameMap",
    ) -> None:
        """Recompute town clusters after a house is placed and announce tier upgrades."""
        old_clusters = game_map.town_clusters

        # Determine the largest cluster any adjacent tile belonged to before this build
        old_max_size = 0
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            old_max_size = max(
                old_max_size,
                old_clusters.get((build_row + dr, build_col + dc), 0),
            )
        old_tier_idx, _ = self._get_settlement_tier(old_max_size)

        # Recompute all clusters
        new_clusters = compute_town_clusters(game_map.world)
        game_map.town_clusters = new_clusters

        new_size = new_clusters.get((build_row, build_col), 1)
        new_tier_idx, new_tier_name = self._get_settlement_tier(new_size)

        if new_tier_idx > old_tier_idx and new_tier_idx > 0:
            tile_cx = build_col * TILE + TILE // 2
            tile_cy = build_row * TILE + TILE // 2

            # Tier-up announcement
            self.floats.append(
                FloatingText(
                    tile_cx,
                    tile_cy - 40,
                    f"{new_tier_name}!",
                    (255, 220, 80),
                    player.current_map,
                )
            )
            for _ in range(25):
                self.particles.append(
                    Particle(tile_cx, tile_cy, (255, 200, 60), player.current_map)
                )

            # Gameplay bonuses scale with tier
            bonus_workers = new_tier_idx
            bonus_resources = {
                1: {"Dirt": 20},
                2: {"Dirt": 40, "Stone": 20},
                3: {"Dirt": 60, "Stone": 40, "Iron": 10},
                4: {"Stone": 60, "Iron": 30, "Gold": 10},
                5: {"Iron": 50, "Gold": 30, "Diamond": 5},
            }.get(new_tier_idx, {})

            for res, qty in bonus_resources.items():
                player.inventory[res] = player.inventory.get(res, 0) + qty

            home = player.current_map
            home_scene_s = self.maps.get(home)
            for _ in range(bonus_workers):
                workers_on_map = len(home_scene_s.workers) if home_scene_s is not None else 0
                if workers_on_map < 5 and home_scene_s is not None:
                    home_scene_s.workers.append(
                        Worker(
                            tile_cx, tile_cy, player_id=player.player_id, home_map=home
                        )
                    )

            if bonus_resources:
                res_text = ", ".join(f"+{v} {k}" for k, v in bonus_resources.items())
                self.floats.append(
                    FloatingText(
                        tile_cx,
                        tile_cy - 56,
                        res_text,
                        (120, 255, 120),
                        player.current_map,
                    )
                )

    def _draw_house_tile(
        self,
        tx: int,
        ty: int,
        tier: int,
        n: bool,
        s: bool,
        e: bool,
        w: bool,
        ticks: int,
    ) -> None:
        """Draw a house tile styled to its settlement tier.

        Args:
            tx, ty: top-left screen position of the tile
            tier: 0=Cottage, 1=Hamlet, 2=Village, 3=Town, 4=Large Town, 5=City
            n, s, e, w: True if that direction has an adjacent house tile
            ticks: pygame.time.get_ticks() for animations
        """
        sc = self.screen

        if tier == 0:
            # -- Isolated Cottage --
            pygame.draw.rect(sc, (180, 120, 60), (tx + 4, ty + 12, 24, 18))
            pygame.draw.polygon(
                sc,
                (160, 40, 40),
                [(tx + 2, ty + 12), (tx + 16, ty + 2), (tx + 30, ty + 12)],
            )
            pygame.draw.rect(sc, (100, 60, 30), (tx + 12, ty + 19, 8, 11))
            pygame.draw.rect(sc, (180, 220, 255), (tx + 7, ty + 15, 5, 5))
            pygame.draw.rect(sc, (80, 60, 40), (tx + 7, ty + 15, 5, 5), 1)

        elif tier == 1:
            # -- Hamlet: warm cottage with chimney, wood grain, amber window --
            wall_c = (185, 130, 70)
            roof_c = (178, 55, 55)
            pygame.draw.rect(sc, wall_c, (tx + 3, ty + 11, 26, 19))
            # Wood-grain horizontal lines
            for ly in range(ty + 15, ty + 30, 4):
                pygame.draw.line(sc, (150, 100, 45), (tx + 3, ly), (tx + 29, ly), 1)
            # Roof
            if n:
                pygame.draw.rect(sc, roof_c, (tx + 3, ty + 7, 26, 5))
            else:
                pygame.draw.polygon(
                    sc,
                    roof_c,
                    [(tx + 1, ty + 11), (tx + 16, ty + 1), (tx + 31, ty + 11)],
                )
            # Chimney
            pygame.draw.rect(sc, (120, 100, 85), (tx + 21, ty + 3, 4, 9))
            pygame.draw.rect(sc, (90, 80, 70), (tx + 20, ty + 2, 6, 3))
            # Door with arch top
            pygame.draw.rect(sc, (110, 65, 30), (tx + 12, ty + 21, 8, 9))
            pygame.draw.ellipse(sc, (110, 65, 30), (tx + 11, ty + 17, 10, 8))
            # Amber lit window
            pygame.draw.rect(sc, (255, 215, 120), (tx + 5, ty + 14, 5, 5))
            pygame.draw.rect(sc, (80, 60, 40), (tx + 5, ty + 14, 5, 5), 1)
            # Second window (right side)
            pygame.draw.rect(sc, (255, 215, 120), (tx + 22, ty + 14, 5, 5))
            pygame.draw.rect(sc, (80, 60, 40), (tx + 22, ty + 14, 5, 5), 1)
            # Path connectors on linked sides
            path_c = (175, 158, 128)
            if s:
                pygame.draw.rect(sc, path_c, (tx + 13, ty + 30, 6, 2))
            if e:
                pygame.draw.rect(sc, path_c, (tx + 30, ty + 22, 2, 5))
            if w:
                pygame.draw.rect(sc, path_c, (tx, ty + 22, 2, 5))

        elif tier == 2:
            # -- Village: row-house with brick walls, parapet, double windows --
            wall_c = (195, 105, 55)  # orange brick
            brick_c = (155, 78, 38)  # mortar / darker brick
            roof_c = (160, 82, 60)  # terracotta parapet
            # Wall extends to adjacent sides seamlessly
            lx = tx if w else tx + 3
            rx = tx + 32 if e else tx + 29
            ty2 = ty if n else ty + 6
            by2 = ty + 32 if s else ty + 30
            pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
            # Brick mortar lines
            for ly in range(ty2 + 5, by2, 5):
                pygame.draw.line(sc, brick_c, (lx, ly), (rx, ly), 1)
            # Parapet / roof on exposed north
            if not n:
                pygame.draw.rect(sc, roof_c, (lx, ty2 - 4, rx - lx, 5))
                for bx in range(lx, rx, 6):
                    pygame.draw.rect(sc, (130, 65, 45), (bx, ty2 - 7, 4, 3))
            # Two windows side by side
            for wx in (tx + 5, tx + 20):
                pygame.draw.rect(sc, (200, 225, 255), (wx, ty + 10, 6, 8))
                pygame.draw.line(
                    sc, (130, 100, 75), (wx + 3, ty + 10), (wx + 3, ty + 18), 1
                )
            # Arched doorway on south-exposed face
            if not s:
                pygame.draw.rect(sc, (105, 58, 28), (tx + 13, ty + 22, 6, 8))
                pygame.draw.ellipse(sc, (105, 58, 28), (tx + 11, ty + 18, 10, 8))

        elif tier == 3:
            # -- Town: stone walls, slate parapet with crenellations, 4-window grid --
            wall_c = (130, 125, 118)  # stone gray
            stone_c = (108, 104, 98)  # stone shadow
            roof_c = (88, 90, 102)  # slate
            lx = tx if w else tx + 2
            rx = tx + 32 if e else tx + 30
            ty2 = ty if n else ty + 3
            by2 = ty + 32 if s else ty + 30
            pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
            # Stone block texture (horizontal courses)
            for iy in range(ty2 + 6, by2, 7):
                pygame.draw.line(sc, stone_c, (lx, iy), (rx, iy), 1)
            # Vertical joints (offset each row)
            row_i = 0
            for iy in range(ty2 + 6, by2, 7):
                offset = 5 if row_i % 2 == 0 else 1
                for ix in range(lx + offset, rx, 10):
                    pygame.draw.line(sc, stone_c, (ix, iy - 6), (ix, iy), 1)
                row_i += 1
            # Slate roof + crenellations on exposed north
            if not n:
                pygame.draw.rect(sc, roof_c, (lx, ty2 - 5, rx - lx, 6))
                for bx in range(lx, rx, 5):
                    pygame.draw.rect(sc, (68, 70, 82), (bx, ty2 - 8, 3, 3))
            # 2×2 window grid
            win_c = (145, 175, 215)
            for wy, wx in [
                (ty + 8, tx + 5),
                (ty + 8, tx + 19),
                (ty + 18, tx + 5),
                (ty + 18, tx + 19),
            ]:
                pygame.draw.rect(sc, win_c, (wx, wy, 5, 6))
                pygame.draw.line(sc, (85, 110, 150), (wx + 2, wy), (wx + 2, wy + 6), 1)
                pygame.draw.line(sc, (85, 110, 150), (wx, wy + 3), (wx + 5, wy + 3), 1)
            # Recessed door
            if not s:
                pygame.draw.rect(sc, (55, 42, 28), (tx + 12, ty + 23, 8, 7))

        elif tier == 4:
            # -- Large Town: deep red brick, multi-row windows, iron roof, awning --
            wall_c = (158, 78, 65)  # deep red brick
            brick_c = (122, 55, 44)  # dark mortar
            roof_c = (55, 58, 68)  # iron grey
            lx = tx if w else tx + 1
            rx = tx + 32 if e else tx + 31
            ty2 = ty if n else ty + 2
            by2 = ty + 32 if s else ty + 31
            pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
            # Dense brick courses
            for iy in range(ty2 + 4, by2, 5):
                pygame.draw.line(sc, brick_c, (lx, iy), (rx, iy), 1)
            # Brick bonds (alternating vertical joints)
            row_i = 0
            for iy in range(ty2 + 4, by2, 5):
                offset = 4 if row_i % 2 == 0 else 0
                for ix in range(lx + offset, rx, 8):
                    pygame.draw.line(sc, brick_c, (ix, iy - 4), (ix, iy), 1)
                row_i += 1
            # Iron roof parapet
            if not n:
                pygame.draw.rect(sc, roof_c, (lx, ty2 - 4, rx - lx, 5))
                for bx in range(lx, rx, 4):
                    pygame.draw.rect(sc, (35, 38, 48), (bx, ty2 - 6, 2, 2))
            # 3 rows × 2 columns of windows
            win_c = (185, 205, 245)
            for wy in (ty + 4, ty + 13, ty + 22):
                for wx in (tx + 5, tx + 21):
                    pygame.draw.rect(sc, win_c, (wx, wy, 5, 7))
                    pygame.draw.line(
                        sc, (130, 150, 200), (wx + 2, wy), (wx + 2, wy + 7), 1
                    )
                    pygame.draw.line(
                        sc, (130, 150, 200), (wx, wy + 3), (wx + 5, wy + 3), 1
                    )
            # Merchant awning on exposed south
            if not s:
                pygame.draw.rect(sc, (195, 85, 55), (tx + 3, ty + 24, 26, 3))
                for ax in range(tx + 3, tx + 29, 4):
                    pygame.draw.line(
                        sc, (220, 100, 70), (ax, ty + 24), (ax + 2, ty + 27), 1
                    )

        else:
            # -- City (tier 5): dark slate, gothic arch windows, spire --
            pulse = int(math.sin(ticks * 0.002) * 10)
            wall_c = (72, 78, 95)  # slate blue-grey
            stone_c = (56, 62, 78)  # deep shadow
            roof_c = (38, 42, 58)  # dark steel
            gold_c = (200, 170, 80 + pulse)  # animated gold trim
            lx = tx
            rx = tx + 32
            ty2 = ty
            by2 = ty + 32
            pygame.draw.rect(sc, wall_c, (lx, ty2, rx - lx, by2 - ty2))
            # Stone block grid
            for iy in range(ty2 + 5, by2, 6):
                for ix in range(lx, rx, 9):
                    pygame.draw.rect(sc, stone_c, (ix, iy, 8, 5), 1)
            # Spire on exposed north
            if not n:
                mid = tx + 16
                pygame.draw.polygon(
                    sc,
                    roof_c,
                    [
                        (mid - 3, ty2),
                        (mid + 3, ty2),
                        (mid + 1, ty2 - 9),
                        (mid - 1, ty2 - 9),
                    ],
                )
                pygame.draw.polygon(
                    sc,
                    gold_c,
                    [(mid - 1, ty2 - 9), (mid + 1, ty2 - 9), (mid, ty2 - 14)],
                )
                pygame.draw.rect(sc, roof_c, (lx, ty2 - 4, rx - lx, 5))
                # Gold crenellation trim
                for bx in range(lx, rx, 5):
                    pygame.draw.rect(sc, gold_c, (bx, ty2 - 5, 3, 2))
            # Gothic arch windows (3 rows × 2 cols)
            win_c = (110, 145, 205)
            for wy in (ty + 3, ty + 13, ty + 21):
                for wx in (tx + 4, tx + 21):
                    # Arch body
                    pygame.draw.rect(sc, win_c, (wx, wy + 3, 6, 6))
                    pygame.draw.ellipse(sc, win_c, (wx, wy, 6, 6))
                    # Gold arch trim
                    pygame.draw.ellipse(sc, gold_c, (wx, wy, 6, 6), 1)
            # Iron-bound door on exposed south
            if not s:
                pygame.draw.rect(sc, (40, 32, 22), (tx + 12, ty + 24, 8, 8))
                pygame.draw.ellipse(sc, (40, 32, 22), (tx + 11, ty + 20, 10, 8))
                pygame.draw.ellipse(sc, gold_c, (tx + 11, ty + 20, 10, 8), 1)

    def _nearest_living_player(
        self, map_key: str | tuple, enemy: Enemy
    ) -> Player | None:
        """Return the nearest living player on map_key, or None if none present."""
        candidates = [
            p
            for p in (self.player1, self.player2)
            if p.current_map == map_key and not p.is_dead
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda p: math.hypot(p.x - enemy.x, p.y - enemy.y))

    def check_cave_transitions(
        self, player: Player, current_map: GameMap | None
    ) -> None:
        """Check if player stepped on a cave entrance and transition if so."""
        # Cave entry is only possible when on a surface map (not already in a cave)
        if isinstance(player.current_map, tuple) and len(player.current_map) == 2:
            return  # already in a cave

        if current_map is None:
            return

        # Caves only exist on the overland tileset, not pure-ocean sector maps
        if current_map.tileset != "overland":
            return

        tile_col = int(player.x) // TILE
        tile_row = int(player.y) // TILE

        if not (0 <= tile_col < WORLD_COLS and 0 <= tile_row < WORLD_ROWS):
            return

        tile_id = current_map.get_tile(tile_row, tile_col)

        # Check if standing on a cave entrance
        if tile_id in (CAVE_MOUNTAIN, CAVE_HILL):
            # Generate or load the cave map
            cave_key = (tile_col, tile_row)
            if cave_key not in self.maps:
                surface_biome = getattr(current_map, "biome", BiomeType.STANDARD)
                env = CaveEnvironment(
                    tile_col, tile_row, cave_type=tile_id, biome=surface_biome
                )
                self.maps[cave_key] = MapScene(env.generate())

            cave_map = self.maps[cave_key]
            # Record the origin map so the exit knows where to return
            cave_map.origin_map = player.current_map
            # Teleport player to cave spawn point (away from exit)
            player.x = cave_map.spawn_col * TILE + TILE // 2
            player.y = cave_map.spawn_row * TILE + TILE // 2
            player.current_map = cave_key

            self._snap_camera_to_player(player)
            self.floats.append(
                FloatingText(
                    player.x,
                    player.y - 30,
                    "Entered cave!",
                    (100, 150, 255),
                    player.current_map,
                )
            )

    def check_cave_exits(self, player: Player, current_map: GameMap | None) -> None:
        """Check if player stepped on a cave exit and transition back to their origin map."""
        # Must be in a cave (2-tuple key)
        if not (isinstance(player.current_map, tuple) and len(player.current_map) == 2):
            return

        if current_map is None:
            return

        # Check if player is standing on a CAVE_EXIT tile
        if not hasattr(current_map, "entrance_col"):
            return

        tile_col = int(player.x) // TILE
        tile_row = int(player.y) // TILE

        tile_id = current_map.get_tile(tile_row, tile_col)
        if tile_id == CAVE_EXIT:
            # Return to the map the player came from
            origin_key = getattr(current_map, "origin_map", "overland")
            origin_map = self.maps.get(origin_key)
            if origin_map is None:
                # Origin sector was evicted — fall back to overland
                origin_key = "overland"
                origin_map = self.maps["overland"]

            entrance_col = current_map.entrance_col
            entrance_row = current_map.entrance_row

            # Find a walkable adjacent tile that isn't a cave entrance
            placed = False
            for dr, dc in [
                (1, 0),
                (-1, 0),
                (0, 1),
                (0, -1),
                (1, 1),
                (-1, -1),
                (1, -1),
                (-1, 1),
            ]:
                adj_c = entrance_col + dc
                adj_r = entrance_row + dr
                if 0 <= adj_c < origin_map.cols and 0 <= adj_r < origin_map.rows:
                    adj_tile = origin_map.get_tile(adj_r, adj_c)
                    if adj_tile not in (WATER, MOUNTAIN, CAVE_MOUNTAIN, CAVE_HILL):
                        player.x = adj_c * TILE + TILE // 2
                        player.y = adj_r * TILE + TILE // 2
                        placed = True
                        break
            if not placed:
                # Fallback: place on the entrance tile anyway
                player.x = entrance_col * TILE + TILE // 2
                player.y = entrance_row * TILE + TILE // 2

            player.current_map = origin_key

            self._snap_camera_to_player(player)
            self.floats.append(
                FloatingText(
                    player.x,
                    player.y - 30,
                    "Exited cave!",
                    (100, 255, 150),
                    player.current_map,
                )
            )

    # -- update ------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Update game state (both players, shared world)."""
        # Update viewport sizes to match actual screen, just like draw() does
        screen_width, screen_height = self.screen.get_size()
        self.viewport_w = screen_width // 2
        self.viewport_h = screen_height

        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()

        # Get player maps
        map1 = self.get_player_current_map(self.player1)
        map2 = self.get_player_current_map(self.player2)

        # Update maps after potential transitions

        # -- Sector-wipe animation tick ------------------------------------
        for pid in list(self.sector_wipe.keys()):
            self.sector_wipe[pid]["progress"] += dt / SECTOR_WIPE_DURATION
            if self.sector_wipe[pid]["progress"] >= 1.0:
                del self.sector_wipe[pid]
        # -- Portal-warp animation tick ------------------------------------
        for pid in list(self.portal_warp.keys()):
            self.portal_warp[pid]["progress"] += dt / PORTAL_WARP_DURATION
            if self.portal_warp[pid]["progress"] >= 1.0:
                del self.portal_warp[pid]
        # -- Sky-view animation tick ---------------------------------------
        _SKY_ANIM_DURATION = 120.0  # frames at dt=1 (≈2 s at 60 fps)
        for pid in (1, 2):
            anim = self._sky_anim[pid]
            if anim is None:
                continue
            anim["progress"] += dt / _SKY_ANIM_DURATION
            if anim["phase"] == "ascend" and anim["progress"] >= 1.0:
                anim["phase"] = "sky"
                anim["progress"] = 0.0
            elif anim["phase"] == "descend" and anim["progress"] >= 1.0:
                self._sky_view[pid] = False
                self._sky_anim[pid] = None
        # -- Sign display timer tick ---------------------------------------
        for pid in (1, 2):
            disp = self._sign_display[pid]
            if disp is not None:
                disp["timer"] -= dt / 60.0  # dt≈1 at 60fps → decrement ~1/60 s
                if disp["timer"] <= 0:
                    self._sign_display[pid] = None
        # -- Cloud drift tick ---------------------------------------------
        for cloud in self._sky_clouds:
            cloud["x"] += cloud["speed"] * dt
        # ----------------------------------------------------------------

        # -- Sector transitions for on-boat players -----------------------
        if not self.player1.is_dead:
            self.check_sector_transitions(self.player1)
        if not self.player2.is_dead:
            self.check_sector_transitions(self.player2)
        # ----------------------------------------------------------------

        # -- Biome entry damage timer tick --------------------------------
        for player in (self.player1, self.player2):
            if player.is_dead:
                continue
            pid = player.player_id
            warn = self._biome_warn_timers[pid]
            if warn is None:
                continue
            warn["frames"] -= dt
            if warn["frames"] <= 0:
                if not self._check_biome_entry_armor(player, warn["biome"]):
                    player.take_damage(
                        5, self.particles, self.floats, player.current_map
                    )
                    if player.hp <= 0 and not player.is_dead:
                        self._start_death_challenge(player)
                self._biome_warn_timers[pid] = None
        # ----------------------------------------------------------------

        # -- Portal lava damage -------------------------------------------
        for player in (self.player1, self.player2):
            if player.is_dead:
                continue
            pid = player.player_id
            if player.current_map != ("portal_realm",):
                self._lava_hurt_timers[pid] = 0
                continue
            cur_map = self.get_player_current_map(player)
            if cur_map is None:
                continue
            pc = int(player.x) // TILE
            pr = int(player.y) // TILE
            if cur_map.get_tile(pr, pc) == PORTAL_LAVA and not self._has_ancient_armor(
                player
            ):
                self._lava_hurt_timers[pid] -= dt
                if self._lava_hurt_timers[pid] <= 0:
                    self._lava_hurt_timers[pid] = 60
                    self.floats.append(
                        FloatingText(
                            int(player.x),
                            int(player.y) - 30,
                            "Lava burns! Need Ancient armor!",
                            (255, 120, 30),
                            player.current_map,
                        )
                    )
                    player.take_damage(
                        8, self.particles, self.floats, player.current_map
                    )
                    if player.hp <= 0 and not player.is_dead:
                        self._start_death_challenge(player)
            else:
                self._lava_hurt_timers[pid] = 0
        # ----------------------------------------------------------------

        # -- Biome entry damage timer tick --------------------------------
        for player in (self.player1, self.player2):
            if player.is_dead:
                continue
            pid = player.player_id
            warn = self._biome_warn_timers[pid]
            if warn is None:
                continue
            warn["frames"] -= dt
            if warn["frames"] <= 0:
                # Grace period expired — deal damage if still unprotected
                if not self._check_biome_entry_armor(player, warn["biome"]):
                    player.take_damage(
                        5, self.particles, self.floats, player.current_map
                    )
                    if player.hp <= 0 and not player.is_dead:
                        self._start_death_challenge(player)
                self._biome_warn_timers[pid] = None
        # ----------------------------------------------------------------

        # -- Portal lava damage -------------------------------------------
        for player in (self.player1, self.player2):
            if player.is_dead:
                continue
            if player.current_map != ("portal_realm",):
                self._lava_hurt_timers[player.player_id] = 0
                continue
            cur_map = self.get_player_current_map(player)
            if cur_map is None:
                continue
            pc = int(player.x) // TILE
            pr = int(player.y) // TILE
            if cur_map.get_tile(pr, pc) == PORTAL_LAVA:
                if not self._has_ancient_armor(player):
                    pid = player.player_id
                    self._lava_hurt_timers[pid] -= dt
                    if self._lava_hurt_timers[pid] <= 0:
                        self._lava_hurt_timers[pid] = 60
                        self.floats.append(
                            FloatingText(
                                int(player.x),
                                int(player.y) - 30,
                                "Lava burns! Need Ancient armor!",
                                (255, 120, 30),
                                player.current_map,
                            )
                        )
                        player.take_damage(
                            8, self.particles, self.floats, player.current_map
                        )
                        if player.hp <= 0 and not player.is_dead:
                            self._start_death_challenge(player)
            else:
                self._lava_hurt_timers[player.player_id] = 0
        # ----------------------------------------------------------------

        # -- Boat disembark detection (before movement) -------------------
        for player in (self.player1, self.player2):
            if player.is_dead or not player.on_boat:
                continue
            cur_map = self.get_player_current_map(player)
            if cur_map is None:
                continue
            pc = int(player.x) // TILE
            pr = int(player.y) // TILE
            if cur_map.get_tile(pr, pc) == WATER:
                # Track the last water tile while sailing
                player.boat_col = pc
                player.boat_row = pr
            else:
                player.on_boat = False
                # Restore the boat tile at the last water position
                if player.boat_col is not None and player.boat_row is not None:
                    cur_map.set_tile(player.boat_row, player.boat_col, BOAT)
                    cur_map.set_tile_hp(player.boat_row, player.boat_col, 0)
                    player.boat_col = None
                    player.boat_row = None
                # Snap centre to the middle of the land tile so no part of the
                # hitbox overlaps water when collision resumes next movement step
                player.x = pc * TILE + TILE // 2
                player.y = pr * TILE + TILE // 2
        # ----------------------------------------------------------------

        # Player 1 movement & mining (skipped while dead or crafting/equip menu open)
        if (
            not self.player1.is_dead
            and self.craft_menus[1] is None
            and self.equip_menus[1] is None
        ):
            if self.player1.on_mount:
                # Drive the mounted creature with player input
                mount1 = self._player_mounts[1]
                if mount1 is not None:
                    cs1 = self.player1.controls.move_keys
                    dx1 = (keys[cs1["right"]] - keys[cs1["left"]]) * 1.0
                    dy1 = (keys[cs1["down"]] - keys[cs1["up"]]) * 1.0
                    mount1.update_riding(dx1, dy1, dt, map1.world)
                    self.player1.x = mount1.x
                    self.player1.y = mount1.y
            else:
                p1_speed_mult = 1.0 + self.player1.active_effects().get(
                    AccessoryEffect.SPEED_BOOST, 0.0
                )
                base_speed1 = self.player1.speed
                self.player1.speed = base_speed1 * p1_speed_mult
                self.player1.update_movement(keys, dt, map1.world)
                self.player1.speed = base_speed1
            self.player1.update_mining(
                keys,
                mouse_buttons,
                dt,
                map1.world,
                map1.tile_hp,
                self.cam1_x,
                self.cam1_y,
                self.particles,
                self.floats,
                self.player1.current_map,
            )
        if not self.player1.is_dead:
            if self.player1.hurt_timer > 0:
                self.player1.hurt_timer -= dt

        # Player 2 movement & mining (skipped while dead or crafting/equip menu open)
        if (
            not self.player2.is_dead
            and self.craft_menus[2] is None
            and self.equip_menus[2] is None
        ):
            if self.player2.on_mount:
                # Drive the mounted creature with player input
                mount2 = self._player_mounts[2]
                if mount2 is not None:
                    cs2 = self.player2.controls.move_keys
                    dx2 = (keys[cs2["right"]] - keys[cs2["left"]]) * 1.0
                    dy2 = (keys[cs2["down"]] - keys[cs2["up"]]) * 1.0
                    mount2.update_riding(dx2, dy2, dt, map2.world)
                    self.player2.x = mount2.x
                    self.player2.y = mount2.y
            else:
                p2_speed_mult = 1.0 + self.player2.active_effects().get(
                    AccessoryEffect.SPEED_BOOST, 0.0
                )
                base_speed2 = self.player2.speed
                self.player2.speed = base_speed2 * p2_speed_mult
                self.player2.update_movement(keys, dt, map2.world)
                self.player2.speed = base_speed2
            self.player2.update_mining(
                keys,
                mouse_buttons,
                dt,
                map2.world,
                map2.tile_hp,
                self.cam2_x,
                self.cam2_y,
                self.particles,
                self.floats,
                self.player2.current_map,
            )
        if not self.player2.is_dead:
            if self.player2.hurt_timer > 0:
                self.player2.hurt_timer -= dt

        # -- Boat boarding detection --------------------------------------
        for player in (self.player1, self.player2):
            if player.is_dead or player.on_boat:
                continue
            cur_map = self.get_player_current_map(player)
            if cur_map is None:
                continue
            pc = int(player.x) // TILE
            pr = int(player.y) // TILE
            if cur_map.get_tile(pr, pc) == BOAT:
                player.on_boat = True
                player.boat_col = pc
                player.boat_row = pr
                cur_map.set_tile(pr, pc, WATER)
                cur_map.set_tile_hp(pr, pc, 0)
                self.floats.append(
                    FloatingText(
                        int(player.x),
                        int(player.y) - 20,
                        "On the boat!",
                        (100, 200, 255),
                        player.current_map,
                    )
                )
        # ----------------------------------------------------------------

        # Workers, pets, creatures — all iterate per-scene so entities are always
        # in the context of the map they live on.
        for scene in self.maps.values():
            for w in scene.workers:
                target_player = self.player1 if w.player_id == 1 else self.player2
                w.update(
                    dt,
                    scene.world,
                    scene.tile_hp,
                    target_player.inventory,
                    scene.particles,
                    scene.floats,
                    w.home_map,
                )
                xp_mult = 1.0 + target_player.active_effects().get(
                    AccessoryEffect.XP_BOOST, 0.0
                )
                target_player.xp += int(w.xp_earned * xp_mult)
                w.xp_earned = 0

        for scene in self.maps.values():
            for pet in scene.pets:
                p1_here = self.player1.current_map == pet.home_map
                p2_here = self.player2.current_map == pet.home_map
                if not p1_here and not p2_here:
                    continue
                if p1_here and p2_here:
                    dist1 = math.hypot(pet.x - self.player1.x, pet.y - self.player1.y)
                    dist2 = math.hypot(pet.x - self.player2.x, pet.y - self.player2.y)
                    target = self.player1 if dist1 < dist2 else self.player2
                elif p1_here:
                    target = self.player1
                else:
                    target = self.player2
                pet.update(dt, target.x, target.y, scene.world)

        for scene in self.maps.values():
            for sc in scene.creatures:
                if sc.rider_id is not None:
                    continue  # ridden creatures are driven by player input instead
                sc.update(dt, scene.world)

        # Enemies
        self._update_enemies(dt)
        self._spawn_portal_guardians()

        # Weapon firing (for both players)
        self._update_combat(keys, mouse_buttons, dt)

        # Projectiles & XP (for both players)
        self._update_projectiles(dt)
        scene1 = self.maps.get(self.player1.current_map)
        if scene1 is not None:
            self.player1.check_level_up(scene1.particles, scene1.floats, self.player1.current_map)
        scene2 = self.maps.get(self.player2.current_map)
        if scene2 is not None:
            self.player2.check_level_up(scene2.particles, scene2.floats, self.player2.current_map)

        # Cameras
        self.cam1_x += (self.player1.x - self.viewport_w // 2 - self.cam1_x) * 0.1
        self.cam1_y += (self.player1.y - self.viewport_h // 2 - self.cam1_y) * 0.1
        self.cam2_x += (self.player2.x - self.viewport_w // 2 - self.cam2_x) * 0.1
        self.cam2_y += (self.player2.y - self.viewport_h // 2 - self.cam2_y) * 0.1

        # Clamp cameras to world bounds (each player might be on different size map)
        map1 = self.get_player_current_map(self.player1)
        map2 = self.get_player_current_map(self.player2)

        world1_pixel_w = map1.cols * TILE if map1 else WORLD_COLS * TILE
        world1_pixel_h = map1.rows * TILE if map1 else WORLD_ROWS * TILE
        world2_pixel_w = map2.cols * TILE if map2 else WORLD_COLS * TILE
        world2_pixel_h = map2.rows * TILE if map2 else WORLD_ROWS * TILE

        self.cam1_x = max(0, min(self.cam1_x, world1_pixel_w - self.viewport_w))
        self.cam1_y = max(0, min(self.cam1_y, world1_pixel_h - self.viewport_h))
        self.cam2_x = max(0, min(self.cam2_x, world2_pixel_w - self.viewport_w))
        self.cam2_y = max(0, min(self.cam2_y, world2_pixel_h - self.viewport_h))

        # Effects — update and cull per-scene
        for scene in self.maps.values():
            for par in scene.particles:
                par.update()
            scene.particles = [par for par in scene.particles if par.life > 0]
            for f in scene.floats:
                f.update()
            scene.floats = [f for f in scene.floats if f.life > 0]

        # Tick treasure reveals
        for rev in self.treasure_reveals:
            rev["timer"] -= dt
        self.treasure_reveals = [r for r in self.treasure_reveals if r["timer"] > 0]

    def _spawn_portal_guardians(self) -> None:
        """Spawn Stone Sentinel enemies for combat quests when a player is nearby."""
        for map_key, quest in self.portal_quests.items():
            if quest["type"] != PortalQuestType.COMBAT:
                continue
            if (
                quest["restored"]
                or quest.get("guardian_defeated")
                or quest.get("guardian_spawned")
            ):
                continue
            # Only spawn if a player is currently on this map
            player_present = any(
                p.current_map == map_key and not p.is_dead
                for p in (self.player1, self.player2)
            )
            if not player_present:
                continue
            game_map = self.maps.get(map_key)
            if game_map is None or not hasattr(game_map, "portal_col"):
                continue
            pcol = game_map.portal_col
            prow = game_map.portal_row
            spawn_x = float(pcol * TILE + TILE // 2 + TILE * 2)
            spawn_y = float(prow * TILE + TILE // 2)
            sentinel = Enemy(spawn_x, spawn_y, "stone_sentinel")
            game_map.enemies.append(sentinel)
            quest["guardian_spawned"] = True
            self.floats.append(
                FloatingText(
                    int(spawn_x),
                    int(spawn_y) - 40,
                    "A guardian awakens!",
                    (200, 80, 80),
                    map_key,
                )
            )

    def _update_enemies(self, dt: float) -> None:
        """Update enemies on all maps that have at least one active player."""
        active_maps: set[str | tuple] = {
            p.current_map
            for p in (self.player1, self.player2)
            if not p.is_dead
        }
        for map_key in active_maps:
            scene = self.maps.get(map_key)
            if scene is None:
                continue
            for enemy in scene.enemies:
                target_player = self._nearest_living_player(map_key, enemy)
                if target_player is None:
                    continue
                cam_x = self.cam1_x if target_player is self.player1 else self.cam2_x
                cam_y = self.cam1_y if target_player is self.player1 else self.cam2_y
                enemy.update(
                    dt,
                    target_player.x,
                    target_player.y,
                    cam_x,
                    cam_y,
                    scene.world,
                    scene.particles,
                )
                dmg = enemy.try_attack(target_player.x, target_player.y)
                if dmg > 0:
                    target_player.take_damage(
                        dmg, scene.particles, scene.floats, target_player.current_map
                    )
                    if target_player.hp <= 0 and not target_player.is_dead:
                        self._start_death_challenge(target_player)
            dead = [e for e in scene.enemies if e.hp <= 0]
            scene.enemies = [e for e in scene.enemies if e.hp > 0]
            for dead_e in dead:
                if dead_e.type_key == "stone_sentinel":
                    self._on_sentinel_defeated(map_key)

    def _draw_portal_warp_viewport(
        self,
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
        progress: float,
    ) -> None:
        """Spinning-vortex warp effect for portal transitions.

        Timeline (progress 0→1 over PORTAL_WARP_DURATION seconds):
          0.0 – 0.5 : Dark overlay and 8 purple blades spiral inward, spinning faster.
          0.5        : Peak — bright white-purple flash.
          0.5 – 1.0 : Blades unwind and fade out; overlay lifts.
        """
        import math

        cx = screen_x + view_w // 2
        cy = screen_y + view_h // 2
        # Radius large enough to cover every viewport corner
        radius = int(math.hypot(view_w / 2, view_h / 2)) + 4

        t = progress  # 0 → 1

        # --- Dark overlay (alpha peaks at midpoint) ---
        overlay_alpha = int(210 * math.sin(t * math.pi))
        overlay_alpha = max(0, min(255, overlay_alpha))
        if overlay_alpha > 0:
            overlay = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
            overlay.fill((10, 0, 20, overlay_alpha))
            self.screen.blit(overlay, (screen_x, screen_y))

        # --- Spinning blades ---
        num_blades = 8
        blade_arc = math.pi / num_blades  # each blade subtends this angle
        # 3 full counter-clockwise spins across the whole animation
        base_angle = -t * 3 * 2 * math.pi

        blade_alpha = int(230 * math.sin(t * math.pi))
        blade_alpha = max(0, min(255, blade_alpha))

        if blade_alpha > 0:
            blade_surf = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
            for i in range(num_blades):
                a0 = base_angle + i * (2 * math.pi / num_blades)
                a1 = a0 + blade_arc
                # Lerp radius: blades grow from 0 → full in first half, shrink back in second
                reach = radius * math.sin(t * math.pi)
                local_cx = cx - screen_x
                local_cy = cy - screen_y
                pts = [
                    (local_cx, local_cy),
                    (
                        local_cx + reach * math.cos(a0),
                        local_cy + reach * math.sin(a0),
                    ),
                    (
                        local_cx + reach * math.cos((a0 + a1) / 2) * 1.05,
                        local_cy + reach * math.sin((a0 + a1) / 2) * 1.05,
                    ),
                    (
                        local_cx + reach * math.cos(a1),
                        local_cy + reach * math.sin(a1),
                    ),
                ]
                # Alternate purple and cyan blades
                if i % 2 == 0:
                    color = (140, 30, 220, blade_alpha)
                else:
                    color = (30, 180, 220, blade_alpha)
                pygame.draw.polygon(blade_surf, color, pts)
            self.screen.blit(blade_surf, (screen_x, screen_y))

        # --- Central glow circle ---
        glow_radius = int(radius * 0.18 * math.sin(t * math.pi))
        if glow_radius > 1:
            glow_surf = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
            glow_alpha = int(200 * math.sin(t * math.pi))
            pygame.draw.circle(
                glow_surf,
                (200, 140, 255, glow_alpha),
                (cx - screen_x, cy - screen_y),
                glow_radius,
            )
            self.screen.blit(glow_surf, (screen_x, screen_y))

        # --- White flash spike at midpoint ---
        flash_alpha = int(255 * max(0.0, 1.0 - abs(t - 0.5) / 0.08))
        flash_alpha = max(0, min(255, flash_alpha))
        if flash_alpha > 0:
            flash = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
            flash.fill((255, 230, 255, flash_alpha))
            self.screen.blit(flash, (screen_x, screen_y))

    def _draw_sector_wipe_viewport(
        self, screen_x: int, screen_y: int, view_w: int, view_h: int, progress: float
    ) -> None:
        """Draw a quick scroll-wipe flash when crossing a sector boundary.

        The first half of the animation blurs/fades out the old view with a
        horizontal or vertical white flash; the second half fades into the new
        view which is already rendered behind it.  We overlay a white rect
        whose alpha peaks at midpoint (progress == 0.5) and falls back to 0.
        """
        # Compute alpha: 0 → 255 at progress 0.5 → 0
        alpha = int(255 * (1.0 - abs(progress - 0.5) * 2.0))
        alpha = max(0, min(255, alpha))
        if alpha == 0:
            return
        flash = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
        flash.fill((220, 240, 255, alpha))
        self.screen.blit(flash, (screen_x, screen_y))

    def _update_combat(
        self,
        keys: pygame.key.ScancodeWrapper,
        mouse_buttons: tuple[bool, bool, bool],
        dt: float,
    ) -> None:
        """Handle weapon firing for both players."""
        # Player 1 firing (skipped while dead)
        if self.player1.weapon_cooldown > 0:
            self.player1.weapon_cooldown -= dt
        if not self.player1.is_dead:
            fire_input_p1 = (
                keys[self.player1.controls.fire_key]
                or mouse_buttons[2]
                or self.player1.auto_fire
            )
            if fire_input_p1 and self.player1.weapon_cooldown <= 0:
                wpn = WEAPONS[self.player1.weapon_level]
                dmg_mult1 = 1.0 + self.player1.active_effects().get(
                    AccessoryEffect.DAMAGE_BOOST, 0.0
                )
                wpn_p1 = {**wpn, "damage": int(wpn["damage"] * dmg_mult1)}
                proj = Projectile(
                    self.player1.x,
                    self.player1.y,
                    self.player1.facing_dx,
                    self.player1.facing_dy,
                    wpn_p1,
                    player_id=1,
                    map_key=self.player1.current_map,
                )
                p1_scene = self.maps.get(self.player1.current_map)
                if p1_scene is not None:
                    p1_scene.projectiles.append(proj)
                self.player1.weapon_cooldown = wpn["cooldown"]

        # Player 2 firing (skipped while dead)
        if self.player2.weapon_cooldown > 0:
            self.player2.weapon_cooldown -= dt
        if not self.player2.is_dead:
            fire_input_p2 = (
                keys[self.player2.controls.fire_key] or self.player2.auto_fire
            )
            if fire_input_p2 and self.player2.weapon_cooldown <= 0:
                wpn = WEAPONS[self.player2.weapon_level]
                dmg_mult2 = 1.0 + self.player2.active_effects().get(
                    AccessoryEffect.DAMAGE_BOOST, 0.0
                )
                wpn_p2 = {**wpn, "damage": int(wpn["damage"] * dmg_mult2)}
                proj = Projectile(
                    self.player2.x,
                    self.player2.y,
                    self.player2.facing_dx,
                    self.player2.facing_dy,
                    wpn_p2,
                    player_id=2,
                    map_key=self.player2.current_map,
                )
                p2_scene = self.maps.get(self.player2.current_map)
                if p2_scene is not None:
                    p2_scene.projectiles.append(proj)
                self.player2.weapon_cooldown = wpn["cooldown"]

    def _update_projectiles(self, dt: float) -> None:
        """Update all projectiles per-scene and check for hits."""
        for scene in self.maps.values():
            for proj in scene.projectiles:
                proj.update(dt)
                if proj.alive:
                    proj.check_hits(scene.enemies, scene.particles, scene.floats)
                if proj.player_id == 1:
                    xp_mult1 = 1.0 + self.player1.active_effects().get(
                        AccessoryEffect.XP_BOOST, 0.0
                    )
                    self.player1.xp += int(proj.xp_earned * xp_mult1)
                elif proj.player_id == 2:
                    xp_mult2 = 1.0 + self.player2.active_effects().get(
                        AccessoryEffect.XP_BOOST, 0.0
                    )
                    self.player2.xp += int(proj.xp_earned * xp_mult2)
                proj.xp_earned = 0
            scene.projectiles = [proj for proj in scene.projectiles if proj.alive]

    # -- drawing -----------------------------------------------------------

    def draw(self) -> None:
        """Render split-screen for both players."""
        # Get actual screen dimensions and update viewport sizes
        screen_width, screen_height = self.screen.get_size()
        self.viewport_w = screen_width // 2
        self.viewport_h = screen_height

        # Left side: Player 1
        self._draw_player_view(
            self.player1,
            self.cam1_x,
            self.cam1_y,
            0,
            0,
            self.viewport_w,
            self.viewport_h,
        )

        # Right side: Player 2
        self._draw_player_view(
            self.player2,
            self.cam2_x,
            self.cam2_y,
            self.viewport_w,
            0,
            self.viewport_w,
            self.viewport_h,
        )

        # Separator line
        pygame.draw.line(
            self.screen,
            (100, 100, 100),
            (self.viewport_w, 0),
            (self.viewport_w, screen_height),
            2,
        )

        pygame.display.flip()

    def _draw_player_view(
        self,
        player: Player,
        cam_x: float,
        cam_y: float,
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        """Draw a single player's viewport."""
        self.screen.set_clip(pygame.Rect(screen_x, screen_y, view_w, view_h))

        pid = player.player_id

        # Sky-view overlay replaces the normal world render
        if self._sky_view[pid]:
            self._draw_sky_view(player, screen_x, screen_y, view_w, view_h)
            self.screen.set_clip(None)
            return

        # Get the map the player is currently on
        current_map = self.get_player_current_map(player)
        if current_map is None:
            current_map = self.maps["overland"]

        world_cols = current_map.cols
        world_rows = current_map.rows
        world_pixel_w = world_cols * TILE
        world_pixel_h = world_rows * TILE

        # Stone border colors
        border_outer = (60, 50, 40)  # Dark stone
        border_inner = (100, 85, 70)  # Light stone

        # Left border
        if cam_x < 0:
            border_width = min(view_w, int(-cam_x) + screen_x)
            pygame.draw.rect(
                self.screen, border_outer, (screen_x, screen_y, border_width, view_h)
            )
            # Add decorative bricks
            for by in range(screen_y, screen_y + view_h, 16):
                pygame.draw.rect(
                    self.screen, border_inner, (screen_x + 2, by, border_width - 4, 8)
                )

        # Right border
        if cam_x + view_w > world_pixel_w:
            border_start = max(0, int(world_pixel_w - cam_x) + screen_x)
            border_width = screen_x + view_w - border_start
            pygame.draw.rect(
                self.screen,
                border_outer,
                (border_start, screen_y, border_width, view_h),
            )
            # Add decorative bricks
            for by in range(screen_y, screen_y + view_h, 16):
                pygame.draw.rect(
                    self.screen,
                    border_inner,
                    (border_start + 2, by, border_width - 4, 8),
                )

        # Top border
        if cam_y < 0:
            border_height = min(view_h, int(-cam_y) + screen_y)
            pygame.draw.rect(
                self.screen, border_outer, (screen_x, screen_y, view_w, border_height)
            )
            # Add decorative bricks
            for bx in range(screen_x, screen_x + view_w, 16):
                pygame.draw.rect(
                    self.screen, border_inner, (bx, screen_y + 2, 8, border_height - 4)
                )

        # Bottom border
        if cam_y + view_h > world_pixel_h:
            border_start = max(0, int(world_pixel_h - cam_y) + screen_y)
            border_height = screen_y + view_h - border_start
            pygame.draw.rect(
                self.screen,
                border_outer,
                (screen_x, border_start, view_w, border_height),
            )
            # Add decorative bricks
            for bx in range(screen_x, screen_x + view_w, 16):
                pygame.draw.rect(
                    self.screen,
                    border_inner,
                    (bx, border_start + 2, 8, border_height - 4),
                )

        # Draw terrain for this viewport
        ticks = pygame.time.get_ticks()
        start_col = max(0, int(cam_x) // TILE)
        end_col = min(world_cols, int(cam_x + view_w) // TILE + 2)
        start_row = max(0, int(cam_y) // TILE)
        end_row = min(world_rows, int(cam_y + view_h) // TILE + 2)

        for r in range(start_row, end_row):
            for c in range(start_col, end_col):
                tid = current_map.get_tile(r, c)
                if tid is None:
                    continue
                info = TILE_INFO.get(tid, {})
                # Use tileset-aware color
                tile_color = current_map.get_tileset_color(tid)
                sx = c * TILE - int(cam_x) + screen_x
                sy = r * TILE - int(cam_y) + screen_y
                pygame.draw.rect(self.screen, tile_color, (sx, sy, TILE, TILE))

                if tid == TREE:
                    pygame.draw.rect(
                        self.screen, (100, 70, 30), (sx + 12, sy + 16, 8, 16)
                    )
                    pygame.draw.circle(
                        self.screen, (30, 130, 30), (sx + 16, sy + 12), 12
                    )
                elif tid in (IRON_ORE, GOLD_ORE, DIAMOND_ORE):
                    for ox, oy in [(8, 8), (20, 12), (14, 22), (24, 24)]:
                        bright = [min(255, ch + 80) for ch in info["color"]]
                        pygame.draw.rect(self.screen, bright, (sx + ox, sy + oy, 3, 3))
                elif tid == WATER:
                    wave_off = int(
                        math.sin(pygame.time.get_ticks() * 0.003 + c * 0.7) * 3
                    )
                    pygame.draw.line(
                        self.screen,
                        (60, 150, 230),
                        (sx + 4, sy + 14 + wave_off),
                        (sx + 28, sy + 14 + wave_off),
                        2,
                    )
                elif tid == MOUNTAIN:
                    # Check if this is part of a 2x2 mountain group starting from top-left
                    is_2x2_tl = (
                        c + 1 < world_cols
                        and r + 1 < world_rows
                        and current_map.get_tile(r, c) == MOUNTAIN
                        and current_map.get_tile(r, c + 1) == MOUNTAIN
                        and current_map.get_tile(r + 1, c) == MOUNTAIN
                        and current_map.get_tile(r + 1, c + 1) == MOUNTAIN
                    )

                    # Check if current tile is part of a larger 2x2 block
                    is_part_of_2x2 = False
                    if is_2x2_tl:
                        is_part_of_2x2 = True
                    else:
                        # Check if we're part of a 2x2 block from other positions
                        for dc, dr in [(-1, 0), (0, -1), (-1, -1)]:
                            check_c, check_r = c + dc, r + dr
                            if (
                                check_c >= 0
                                and check_r >= 0
                                and check_c + 1 < world_cols
                                and check_r + 1 < world_rows
                            ):
                                if (
                                    current_map.get_tile(check_r, check_c) == MOUNTAIN
                                    and current_map.get_tile(check_r, check_c + 1)
                                    == MOUNTAIN
                                    and current_map.get_tile(check_r + 1, check_c)
                                    == MOUNTAIN
                                    and current_map.get_tile(check_r + 1, check_c + 1)
                                    == MOUNTAIN
                                ):
                                    is_part_of_2x2 = True
                                    break

                    if is_2x2_tl:
                        # Draw multiple ridge-like peaks for 2x2 mountain groups
                        base_y = sy + TILE * 2
                        block_left_x = sx
                        block_right_x = sx + TILE * 2

                        # Define peaks (x_offset from block_left, height)
                        peaks = [
                            (12, sy - TILE // 3),  # Left-center peak
                            (24, sy - TILE // 5),  # Center-right peak
                            (36, sy - TILE // 3.5),  # Right peak
                        ]

                        # Draw background mountain
                        pygame.draw.polygon(
                            self.screen,
                            (80, 70, 60),
                            [
                                (block_left_x, base_y),
                                (block_left_x + 8, sy + TILE // 2),
                                (block_right_x - 8, sy + TILE // 2),
                                (block_right_x, base_y),
                            ],
                        )

                        # Draw each peak (wider and ridge-like)
                        for peak_x, peak_y in peaks:
                            x = block_left_x + peak_x
                            width = 18  # Width of each ridge peak

                            # Left slope (darker)
                            pygame.draw.polygon(
                                self.screen,
                                (60, 50, 40),
                                [
                                    (x - width, base_y),
                                    (x, peak_y),
                                    (x, base_y),
                                ],
                            )
                            # Right slope (lighter)
                            pygame.draw.polygon(
                                self.screen,
                                (100, 85, 65),
                                [
                                    (x, peak_y),
                                    (x + width, base_y),
                                    (x, base_y),
                                ],
                            )
                            # Wide snow cap on ridge
                            pygame.draw.polygon(
                                self.screen,
                                (245, 250, 255),
                                [
                                    (x - 8, peak_y + 6),
                                    (x, peak_y),
                                    (x + 8, peak_y + 6),
                                ],
                            )
                    elif not is_part_of_2x2:
                        # Draw regular small mountain triangles (only if not part of a 2x2 block)
                        pygame.draw.polygon(
                            self.screen,
                            (110, 100, 90),
                            [
                                (sx + 4, sy + TILE),
                                (sx + 16, sy + 2),
                                (sx + TILE - 4, sy + TILE),
                            ],
                        )
                        pygame.draw.polygon(
                            self.screen,
                            (230, 230, 240),
                            [(sx + 12, sy + 8), (sx + 16, sy + 2), (sx + 20, sy + 8)],
                        )
                        pygame.draw.line(
                            self.screen,
                            (70, 65, 60),
                            (sx + 10, sy + 18),
                            (sx + 14, sy + 12),
                            1,
                        )
                        pygame.draw.line(
                            self.screen,
                            (70, 65, 60),
                            (sx + 20, sy + 20),
                            (sx + 22, sy + 14),
                            1,
                        )
                elif tid == HOUSE:
                    cluster_size = current_map.town_clusters.get((r, c), 1)
                    tier, _ = self._get_settlement_tier(cluster_size)
                    hn = current_map.get_tile(r - 1, c) == HOUSE
                    hs = current_map.get_tile(r + 1, c) == HOUSE
                    he = current_map.get_tile(r, c + 1) == HOUSE
                    hw = current_map.get_tile(r, c - 1) == HOUSE
                    self._draw_house_tile(sx, sy, tier, hn, hs, he, hw, ticks)
                elif tid == PIER:
                    # Wood-plank dock over water
                    plank_c = (155, 115, 50)
                    edge_c = (100, 75, 30)
                    pygame.draw.rect(self.screen, plank_c, (sx + 2, sy + 2, 28, 28))
                    # Plank lines
                    for lx in range(sx + 6, sx + 29, 7):
                        pygame.draw.line(
                            self.screen, edge_c, (lx, sy + 2), (lx, sy + 30), 1
                        )
                    pygame.draw.rect(self.screen, edge_c, (sx + 2, sy + 2, 28, 28), 1)
                elif tid == BOAT:
                    # Small moored boat
                    pygame.draw.polygon(
                        self.screen,
                        (120, 80, 40),
                        [
                            (sx + 4, sy + 18),
                            (sx + 28, sy + 18),
                            (sx + 24, sy + 28),
                            (sx + 8, sy + 28),
                        ],
                    )
                    # Mast
                    pygame.draw.line(
                        self.screen,
                        (80, 55, 25),
                        (sx + 16, sy + 4),
                        (sx + 16, sy + 18),
                        2,
                    )
                    # Sail
                    pygame.draw.polygon(
                        self.screen,
                        (235, 225, 195),
                        [(sx + 17, sy + 5), (sx + 17, sy + 17), (sx + 27, sy + 11)],
                    )
                    # Cabin
                    pygame.draw.rect(
                        self.screen, (160, 110, 55), (sx + 10, sy + 12, 8, 7)
                    )
                    pygame.draw.rect(
                        self.screen, (180, 220, 255), (sx + 12, sy + 13, 3, 3)
                    )
                elif tid == TREASURE_CHEST:
                    # Golden chest with lock
                    chest_body = (185, 130, 40)
                    chest_band = (230, 180, 60)
                    chest_dark = (120, 85, 25)
                    # Body
                    pygame.draw.rect(self.screen, chest_body, (sx + 4, sy + 14, 24, 14))
                    # Lid
                    pygame.draw.rect(self.screen, chest_body, (sx + 4, sy + 8, 24, 8))
                    pygame.draw.polygon(
                        self.screen,
                        chest_band,
                        [
                            (sx + 4, sy + 16),
                            (sx + 28, sy + 16),
                            (sx + 28, sy + 19),
                            (sx + 4, sy + 19),
                        ],
                    )
                    # Lock
                    pygame.draw.rect(self.screen, chest_dark, (sx + 13, sy + 17, 6, 5))
                    pygame.draw.ellipse(
                        self.screen, chest_dark, (sx + 13, sy + 14, 6, 6)
                    )
                    # Shimmer sparkle
                    sp = int(math.sin(ticks * 0.006) * 2) + 2
                    pygame.draw.line(
                        self.screen,
                        (255, 240, 130),
                        (sx + 8, sy + 4 + sp),
                        (sx + 8 + 3, sy + 4 + sp - 3),
                        1,
                    )
                    pygame.draw.line(
                        self.screen,
                        (255, 240, 130),
                        (sx + 8, sy + 4 + sp),
                        (sx + 8 - 3, sy + 4 + sp + 3),
                        1,
                    )
                elif tid in (CAVE_MOUNTAIN, CAVE_HILL):
                    # Draw cave entrance
                    # Darker base color already set by tileset color
                    # Add cave entrance graphics
                    cave_color = tile_color
                    # Draw a shadowy entrance
                    pygame.draw.rect(self.screen, cave_color, (sx + 4, sy + 8, 24, 20))
                    # Add entrance shadow
                    shadow = tuple(max(0, c - 30) for c in cave_color)
                    pygame.draw.polygon(
                        self.screen,
                        shadow,
                        [
                            (sx + 8, sy + 12),
                            (sx + 24, sy + 12),
                            (sx + 20, sy + 20),
                            (sx + 10, sy + 20),
                        ],
                    )
                    # Add some rock detail
                    rock_color = tuple(max(0, min(255, c + 20)) for c in cave_color)
                    pygame.draw.circle(self.screen, rock_color, (sx + 12, sy + 15), 2)
                    pygame.draw.circle(self.screen, rock_color, (sx + 20, sy + 14), 2)
                    pygame.draw.circle(self.screen, rock_color, (sx + 16, sy + 20), 2)
                elif tid == CAVE_EXIT:
                    # Draw cave exit - a glowing portal/ladder
                    # Pulsing glow effect
                    pulse = int(math.sin(pygame.time.get_ticks() * 0.004) * 20 + 40)
                    glow_color = (pulse + 40, pulse + 80, pulse + 40)
                    pygame.draw.rect(self.screen, glow_color, (sx + 4, sy + 2, 24, 28))
                    # Ladder rungs
                    rung_color = (120, 90, 50)
                    for ry in range(6, 28, 6):
                        pygame.draw.line(
                            self.screen,
                            rung_color,
                            (sx + 8, sy + ry),
                            (sx + 24, sy + ry),
                            2,
                        )
                    # Vertical rails
                    pygame.draw.line(
                        self.screen, rung_color, (sx + 8, sy + 4), (sx + 8, sy + 28), 2
                    )
                    pygame.draw.line(
                        self.screen,
                        rung_color,
                        (sx + 24, sy + 4),
                        (sx + 24, sy + 28),
                        2,
                    )
                elif tid == CORAL:
                    # Coral formation: branching pink arms
                    coral_c = info.get("drop_color", (240, 80, 130))
                    bright_c = tuple(min(255, ch + 60) for ch in coral_c)
                    # Central stalk
                    pygame.draw.line(
                        self.screen, coral_c, (sx + 16, sy + 28), (sx + 16, sy + 14), 2
                    )
                    # Left branch
                    pygame.draw.line(
                        self.screen, coral_c, (sx + 16, sy + 20), (sx + 8, sy + 12), 2
                    )
                    pygame.draw.circle(self.screen, bright_c, (sx + 8, sy + 11), 3)
                    # Right branch
                    pygame.draw.line(
                        self.screen, coral_c, (sx + 16, sy + 18), (sx + 24, sy + 10), 2
                    )
                    pygame.draw.circle(self.screen, bright_c, (sx + 24, sy + 9), 3)
                    # Top tip
                    pygame.draw.circle(self.screen, bright_c, (sx + 16, sy + 13), 3)
                elif tid == DIVE_EXIT:
                    # Upward-floating bubbles and chevron indicating surface
                    pulse = int(math.sin(ticks * 0.005) * 15 + 40)
                    glow = (pulse, pulse + 80, min(255, pulse + 120))
                    pygame.draw.rect(self.screen, glow, (sx + 4, sy + 2, 24, 28))
                    # Upward chevron
                    arrow_c = (200, 240, 255)
                    pygame.draw.polygon(
                        self.screen,
                        arrow_c,
                        [(sx + 16, sy + 6), (sx + 10, sy + 14), (sx + 22, sy + 14)],
                    )
                    pygame.draw.polygon(
                        self.screen,
                        arrow_c,
                        [(sx + 16, sy + 14), (sx + 10, sy + 22), (sx + 22, sy + 22)],
                    )
                    # Bubble
                    bub_off = int(math.sin(ticks * 0.004 + 1.5) * 3)
                    pygame.draw.circle(
                        self.screen, (180, 230, 255), (sx + 24, sy + 10 + bub_off), 2
                    )
                elif tid == PORTAL_RUINS:
                    # Crumbled stone ring — partial pillars with gaps and moss tones
                    stone_c = (90, 80, 95)
                    moss_c = (60, 80, 55)
                    # Base slab (worn)
                    pygame.draw.rect(self.screen, stone_c, (sx + 4, sy + 24, 24, 5))
                    # Four partial pillars at corners (some broken)
                    pygame.draw.rect(
                        self.screen, stone_c, (sx + 4, sy + 10, 5, 14)
                    )  # left
                    pygame.draw.rect(
                        self.screen, stone_c, (sx + 23, sy + 14, 5, 10)
                    )  # right (shorter — broken)
                    pygame.draw.rect(
                        self.screen, stone_c, (sx + 10, sy + 6, 5, 18)
                    )  # back-left
                    # Moss accent
                    pygame.draw.rect(self.screen, moss_c, (sx + 4, sy + 10, 3, 3))
                    pygame.draw.rect(self.screen, moss_c, (sx + 23, sy + 14, 3, 2))
                    # Dark center void
                    pygame.draw.rect(
                        self.screen, (25, 20, 30), (sx + 10, sy + 14, 12, 10)
                    )
                elif tid == PORTAL_ACTIVE:
                    # Glowing portal ring with pulsing inner energy
                    pulse = math.sin(ticks * 0.006)
                    stone_c = (110, 95, 125)
                    # Complete stone ring pillars
                    pygame.draw.rect(self.screen, stone_c, (sx + 4, sy + 24, 24, 5))
                    pygame.draw.rect(self.screen, stone_c, (sx + 4, sy + 6, 5, 18))
                    pygame.draw.rect(self.screen, stone_c, (sx + 23, sy + 6, 5, 18))
                    pygame.draw.rect(self.screen, stone_c, (sx + 10, sy + 4, 12, 4))
                    # Inner portal energy
                    energy_r = max(0, min(255, int(140 + pulse * 30)))
                    energy_g = max(0, min(255, int(50 + pulse * 20)))
                    energy_b = max(0, min(255, int(220 + pulse * 35)))
                    pygame.draw.ellipse(
                        self.screen,
                        (energy_r, energy_g, energy_b),
                        (sx + 9, sy + 8, 14, 16),
                    )
                    # Bright centre shimmer
                    inner_b = max(0, min(255, int(200 + pulse * 55)))
                    pygame.draw.ellipse(
                        self.screen, (255, 200, inner_b), (sx + 12, sy + 11, 8, 10)
                    )
                elif tid == ANCIENT_STONE:
                    # Short stone obelisk; pulses yellow if it's the next ritual stone
                    stone_c = (120, 110, 100)
                    # Determine if this is the next stone to activate
                    quest = self.portal_quests.get(player.current_map)
                    is_next = False
                    if (
                        quest
                        and quest["type"] == PortalQuestType.RITUAL
                        and not quest["restored"]
                    ):
                        positions = getattr(current_map, "ritual_stone_positions", [])
                        next_idx = quest["stones_activated"]
                        tile_c_pos = (
                            int(sx + int(cam_x - screen_x)) // TILE if False else c
                        )
                        # c and r are the tile coords from the outer loop
                        if next_idx < len(positions) and positions[next_idx] == (c, r):
                            is_next = True
                    # Obelisk body
                    pygame.draw.rect(self.screen, stone_c, (sx + 11, sy + 12, 10, 16))
                    # Pointed top
                    pygame.draw.polygon(
                        self.screen,
                        stone_c,
                        [(sx + 11, sy + 12), (sx + 21, sy + 12), (sx + 16, sy + 6)],
                    )
                    if is_next:
                        pulse_y = int(math.sin(ticks * 0.01) * 3)
                        pygame.draw.polygon(
                            self.screen,
                            (240, 210, 50),
                            [
                                (sx + 10, sy + 11 + pulse_y),
                                (sx + 22, sy + 11 + pulse_y),
                                (sx + 16, sy + 5 + pulse_y),
                            ],
                            2,
                        )
                    else:
                        # Faint rune markings
                        pygame.draw.line(
                            self.screen,
                            (80, 72, 65),
                            (sx + 14, sy + 14),
                            (sx + 18, sy + 14),
                            1,
                        )
                        pygame.draw.line(
                            self.screen,
                            (80, 72, 65),
                            (sx + 14, sy + 18),
                            (sx + 18, sy + 18),
                            1,
                        )
                elif tid == PORTAL_WALL:
                    # Ancient stone brick pattern (darker base already set by tileset color)
                    brick_c = tile_color
                    mortar_c = tuple(max(0, ch - 20) for ch in brick_c)
                    # Horizontal mortar lines
                    pygame.draw.line(
                        self.screen, mortar_c, (sx, sy + 10), (sx + TILE, sy + 10), 1
                    )
                    pygame.draw.line(
                        self.screen, mortar_c, (sx, sy + 22), (sx + TILE, sy + 22), 1
                    )
                    # Alternating vertical mortar (brick offset pattern)
                    pygame.draw.line(
                        self.screen, mortar_c, (sx + 16, sy), (sx + 16, sy + 10), 1
                    )
                    pygame.draw.line(
                        self.screen, mortar_c, (sx + 8, sy + 10), (sx + 8, sy + 22), 1
                    )
                    pygame.draw.line(
                        self.screen, mortar_c, (sx + 24, sy + 10), (sx + 24, sy + 22), 1
                    )
                    pygame.draw.line(
                        self.screen,
                        mortar_c,
                        (sx + 16, sy + 22),
                        (sx + 16, sy + TILE),
                        1,
                    )
                elif tid == PORTAL_FLOOR:
                    # Flat floor with faint engraved cross/circle pattern
                    etch_c = tuple(max(0, ch - 12) for ch in tile_color)
                    # Faint circle
                    pygame.draw.circle(self.screen, etch_c, (sx + 16, sy + 16), 8, 1)
                    # Cross lines
                    pygame.draw.line(
                        self.screen, etch_c, (sx + 16, sy + 8), (sx + 16, sy + 24), 1
                    )
                    pygame.draw.line(
                        self.screen, etch_c, (sx + 8, sy + 16), (sx + 24, sy + 16), 1
                    )
                elif tid in (SIGN, BROKEN_LADDER, SKY_LADDER):
                    self._draw_world_tile_sprite(tid, sx, sy, ticks)
        # Draw all entities that belong to this scene
        scene = self.maps.get(player.current_map)
        if scene is not None:
            for par in scene.particles:
                par.draw(self.screen, cam_x - screen_x, cam_y - screen_y)
            for f in scene.floats:
                f.draw(self.screen, self.font, cam_x - screen_x, cam_y - screen_y)
            for w in scene.workers:
                w.draw(self.screen, cam_x - screen_x, cam_y - screen_y)
            for pet in scene.pets:
                pet.draw(self.screen, cam_x - screen_x, cam_y - screen_y, ticks)
            for sc in scene.creatures:
                rider_color: tuple[int, int, int] | None = None
                if sc.rider_id is not None:
                    rider = self.player1 if sc.rider_id == 1 else self.player2
                    rider_color = rider.color
                sc.draw(self.screen, cam_x - screen_x, cam_y - screen_y, ticks, rider_color)
            for enemy in scene.enemies:
                enemy.draw(self.screen, cam_x - screen_x, cam_y - screen_y)
            for proj in scene.projectiles:
                proj.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

        # Draw players that share this map
        current_map_key = player.current_map
        for p in (self.player1, self.player2):
            if p.current_map == current_map_key:
                p.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

        self._draw_player_ui(player, screen_x, screen_y, view_w, view_h)
        if player.is_dead:
            self._draw_death_challenge(player, screen_x, screen_y, view_w, view_h)
        self._draw_treasure_reveal(player, screen_x, screen_y, view_w, view_h)
        if self.craft_menus[player.player_id] is not None:
            self._draw_craft_menu(player, screen_x, screen_y, view_w, view_h)
        if self.equip_menus[player.player_id] is not None:
            self._draw_equip_menu(player, screen_x, screen_y, view_w, view_h)

        # Sector-wipe flash overlay (drawn last so it appears on top)
        wipe_state = self.sector_wipe.get(player.player_id)
        if wipe_state:
            self._draw_sector_wipe_viewport(
                screen_x, screen_y, view_w, view_h, wipe_state["progress"]
            )

        # Portal-warp vortex overlay (drawn on top of sector wipe)
        warp_state = self.portal_warp.get(player.player_id)
        if warp_state:
            self._draw_portal_warp_viewport(
                screen_x, screen_y, view_w, view_h, warp_state["progress"]
            )

        self.screen.set_clip(None)

    def _draw_player_ui(
        self, player: Player, screen_x: int, screen_y: int, view_w: int, view_h: int
    ) -> None:
        """Draw UI for a single player's viewport."""
        font_small = self.font_ui_sm
        font_tiny = self.font_ui_xs

        # Top HUD panel — HP, XP, current gear only; inventory/upgrades are in the modal
        top_panel_w = 240
        top_panel_h = 148
        top_panel_surf = pygame.Surface((top_panel_w, top_panel_h), pygame.SRCALPHA)
        top_panel_surf.fill((20, 20, 30, 200))
        self.screen.blit(top_panel_surf, (screen_x + 8, screen_y + 8))
        pygame.draw.rect(
            self.screen,
            (150, 150, 150),
            (screen_x + 8, screen_y + 8, top_panel_w, top_panel_h),
            2,
        )

        # Health bar
        bar_w, bar_h = 220, 18
        hp_ratio = max(0, player.hp / player.max_hp)
        pygame.draw.rect(
            self.screen, (50, 50, 50), (screen_x + 18, screen_y + 18, bar_w, bar_h)
        )
        hp_col = (
            (50, 200, 50)
            if hp_ratio > 0.5
            else (220, 180, 30) if hp_ratio > 0.25 else (220, 40, 40)
        )
        pygame.draw.rect(
            self.screen,
            hp_col,
            (screen_x + 18, screen_y + 18, int(bar_w * hp_ratio), bar_h),
        )
        self.screen.blit(
            font_small.render(
                f"HP: {player.hp:.0f}/{player.max_hp}", True, (255, 255, 255)
            ),
            (screen_x + 25, screen_y + 20),
        )

        # XP bar
        xp_bar_w = 220
        xp_ratio = player.xp / player.xp_next if player.xp_next > 0 else 0
        pygame.draw.rect(
            self.screen, (50, 50, 0), (screen_x + 18, screen_y + 44, xp_bar_w, 10)
        )
        pygame.draw.rect(
            self.screen,
            (255, 255, 0),
            (screen_x + 18, screen_y + 44, int(xp_bar_w * xp_ratio), 10),
        )
        self.screen.blit(
            font_tiny.render(
                f"Lv {player.level}  XP: {player.xp}/{player.xp_next}",
                True,
                (255, 255, 0),
            ),
            (screen_x + 18, screen_y + 56),
        )

        # Current pickaxe
        pick = PICKAXES[player.pick_level]
        pygame.draw.rect(
            self.screen, pick["color"], (screen_x + 18, screen_y + 74, 10, 10)
        )
        pick_label = (
            pick["name"]
            if player.pick_level < len(PICKAXES) - 1
            else f"{pick['name']} (MAX)"
        )
        self.screen.blit(
            font_tiny.render(pick_label, True, (255, 255, 255)),
            (screen_x + 32, screen_y + 73),
        )

        # Current weapon
        wpn = WEAPONS[player.weapon_level]
        pygame.draw.rect(
            self.screen, wpn["color"], (screen_x + 18, screen_y + 90, 10, 10)
        )
        wpn_label = (
            wpn["name"]
            if player.weapon_level < len(WEAPONS) - 1
            else f"{wpn['name']} (MAX)"
        )
        self.screen.blit(
            font_tiny.render(wpn_label, True, (255, 150, 100)),
            (screen_x + 32, screen_y + 89),
        )

        # Defense %
        def_pct = int(player.defense_pct * 100)
        equip_key_name = pygame.key.name(player.controls.equip_key).upper()
        self.screen.blit(
            font_tiny.render(
                f"Defense: {def_pct}%  [{equip_key_name}] Inventory",
                True,
                (160, 220, 160),
            ),
            (screen_x + 18, screen_y + 108),
        )

        # Workers / pets
        parts = []
        workers_here = [
            w
            for sc in self.maps.values()
            for w in sc.workers
            if getattr(w, "player_id", None) == player.player_id
        ]
        if workers_here:
            parts.append(f"Workers: {len(workers_here)}")
        pets_here = [
            p
            for sc in self.maps.values()
            for p in sc.pets
            if getattr(p, "player_id", None) == player.player_id
        ]
        num_cats = sum(1 for p in pets_here if p.kind == "cat")
        num_dogs = sum(1 for p in pets_here if p.kind == "dog")
        if num_cats:
            parts.append(f"Cats: {num_cats}")
        if num_dogs:
            parts.append(f"Dogs: {num_dogs}")
        if parts:
            self.screen.blit(
                font_tiny.render("  ".join(parts), True, (100, 220, 255)),
                (screen_x + 18, screen_y + 126),
            )

        # Bottom HUD Panel (Controls + Auto-toggle status)
        bottom_panel_h = 130
        ctrl_y_start = screen_y + view_h - 138
        bottom_panel_w = 340
        bottom_panel_surf = pygame.Surface(
            (bottom_panel_w, bottom_panel_h), pygame.SRCALPHA
        )
        bottom_panel_surf.fill((20, 20, 30, 200))  # Translucent dark blue-gray
        self.screen.blit(bottom_panel_surf, (screen_x + 8, ctrl_y_start))

        # Bottom panel border
        pygame.draw.rect(
            self.screen,
            (150, 150, 150),
            (screen_x + 8, ctrl_y_start, bottom_panel_w, bottom_panel_h),
            2,
        )

        # Control scheme (2-column layout)
        controls = player.controls.get_controls_list()

        ctrl_y = ctrl_y_start + 8
        ctrl_header = font_small.render("Controls:", True, (200, 200, 200))
        self.screen.blit(ctrl_header, (screen_x + 18, ctrl_y))

        controls_per_column = 3

        column_widths = [0, 90, 210]
        for idx, ctrl_text in enumerate(controls):
            col = idx // controls_per_column
            row = idx % controls_per_column
            x_offset = column_widths[col]
            y_offset = ctrl_y + 24 + row * 15
            ctrl_surf = font_tiny.render(ctrl_text, True, (180, 180, 180))
            self.screen.blit(ctrl_surf, (screen_x + 18 + x_offset, y_offset))

        # Auto-toggle status lines (appended below the controls grid)
        auto_y = ctrl_y + 24 + (controls_per_column - 1) * 15 + 20
        auto_mine_key = pygame.key.name(player.controls.toggle_auto_mine_key).upper()
        auto_mine_status = (
            f"Auto Mine ({auto_mine_key}): {'ON' if player.auto_mine else 'OFF'}"
        )
        auto_mine_color = (100, 255, 100) if player.auto_mine else (150, 150, 150)
        auto_mine_text = font_tiny.render(auto_mine_status, True, auto_mine_color)
        self.screen.blit(auto_mine_text, (screen_x + 18, auto_y))

        auto_fire_key = pygame.key.name(player.controls.toggle_auto_fire_key).upper()
        auto_fire_status = (
            f"Auto Fire ({auto_fire_key}): {'ON' if player.auto_fire else 'OFF'}"
        )
        auto_fire_color = (100, 255, 100) if player.auto_fire else (150, 150, 150)
        auto_fire_text = font_tiny.render(auto_fire_status, True, auto_fire_color)
        self.screen.blit(auto_fire_text, (screen_x + 18, auto_y + 16))

        # Cave interaction hint — shown when standing on a cave entrance or exit
        interact_key = pygame.key.name(player.controls.interact_key).upper()
        current_map_obj = self.get_player_current_map(player)
        if current_map_obj is not None:
            p_col = int(player.x) // TILE
            p_row = int(player.y) // TILE
            tile_id = current_map_obj.get_tile(p_row, p_col)
            if tile_id in (CAVE_MOUNTAIN, CAVE_HILL):
                hint = font_tiny.render(
                    f"[{interact_key}] Enter cave", True, (180, 180, 255)
                )
                hint_x = screen_x + view_w // 2 - hint.get_width() // 2
                hint_y = screen_y + view_h - 150
                self.screen.blit(hint, (hint_x, hint_y))
            elif tile_id == CAVE_EXIT:
                hint = font_tiny.render(
                    f"[{interact_key}] Exit cave", True, (180, 255, 180)
                )
                hint_x = screen_x + view_w // 2 - hint.get_width() // 2
                hint_y = screen_y + view_h - 150
                self.screen.blit(hint, (hint_x, hint_y))
            # Housing environment hints
            elif tile_id == HOUSE and current_map_obj.tileset == "overland":
                cluster_size = current_map_obj.town_clusters.get((p_row, p_col), 1)
                tier_idx, tier_name = self._get_settlement_tier(cluster_size)
                hint = font_tiny.render(
                    f"[{interact_key}] Enter {tier_name}", True, (255, 210, 130)
                )
                hint_x = screen_x + view_w // 2 - hint.get_width() // 2
                hint_y = screen_y + view_h - 150
                self.screen.blit(hint, (hint_x, hint_y))
            elif tile_id == SETTLEMENT_HOUSE:
                hint = font_tiny.render(
                    f"[{interact_key}] Enter house", True, (255, 210, 130)
                )
                hint_x = screen_x + view_w // 2 - hint.get_width() // 2
                hint_y = screen_y + view_h - 150
                self.screen.blit(hint, (hint_x, hint_y))
            elif tile_id == HOUSE_EXIT:
                hint = font_tiny.render(f"[{interact_key}] Exit", True, (180, 255, 180))
                hint_x = screen_x + view_w // 2 - hint.get_width() // 2
                hint_y = screen_y + view_h - 150
                self.screen.blit(hint, (hint_x, hint_y))
            elif tile_id == WORKTABLE or any(
                current_map_obj.get_tile(p_row + dr, p_col + dc) == WORKTABLE
                for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]
            ):
                # Only show craft hint if we're in a housing env (not overland HOUSE tile)
                if self._is_in_housing_env(player):
                    hint = font_tiny.render(
                        f"[{interact_key}] Craft", True, (130, 220, 255)
                    )
                    hint_x = screen_x + view_w // 2 - hint.get_width() // 2
                    hint_y = screen_y + view_h - 150
                    self.screen.blit(hint, (hint_x, hint_y))
            elif any(
                current_map_obj.get_tile(p_row + dr, p_col + dc) == SIGN
                for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]
            ):
                hint = font_tiny.render(
                    f"[{interact_key}] Read sign", True, (230, 200, 120)
                )
                hint_x = screen_x + view_w // 2 - hint.get_width() // 2
                hint_y = screen_y + view_h - 150
                self.screen.blit(hint, (hint_x, hint_y))
            elif any(
                current_map_obj.get_tile(p_row + dr, p_col + dc) == BROKEN_LADDER
                for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]
            ):
                hint = font_tiny.render(
                    f"[{interact_key}] Repair ladder", True, (200, 160, 90)
                )
                hint_x = screen_x + view_w // 2 - hint.get_width() // 2
                hint_y = screen_y + view_h - 150
                self.screen.blit(hint, (hint_x, hint_y))
            elif any(
                current_map_obj.get_tile(p_row + dr, p_col + dc) == SKY_LADDER
                for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]
            ):
                hint = font_tiny.render(
                    f"[{interact_key}] Ascend to sky", True, (140, 200, 255)
                )
                hint_x = screen_x + view_w // 2 - hint.get_width() // 2
                hint_y = screen_y + view_h - 150
                self.screen.blit(hint, (hint_x, hint_y))

        # Sector minimap (top-right corner)
        self._draw_sector_minimap(player, screen_x, screen_y, view_w, view_h)

        # Sign text panel
        self._draw_sign_display(player, screen_x, screen_y, view_w, view_h)

        # Sky-ladder ascend/descend flash overlay
        self._draw_sky_anim_overlay(player, screen_x, screen_y, view_w, view_h)

    def _draw_sector_minimap(
        self, player: Player, screen_x: int, screen_y: int, view_w: int, view_h: int
    ) -> None:
        """Draw a small sector-grid minimap in the top-right corner of the viewport.

        Only shown when the player is on the surface (not in a cave).
        Shows a 9x9 window of the infinite sector grid centred on the player's
        current sector, with visited sectors lit and fog elsewhere.
        """
        player_sector = self._get_player_sector(player)
        if player_sector is None:
            return  # underground — hide minimap

        cx, cy = player_sector  # current sector coords

        CELL = 10  # px per cell
        GAP = 1  # px gap between cells
        WINDOW = 9  # cells across / down (must be odd)
        half = WINDOW // 2

        panel_w = WINDOW * (CELL + GAP) - GAP + 8
        panel_h = WINDOW * (CELL + GAP) - GAP + 8 + 14  # extra 14 for header text
        panel_x = screen_x + view_w - panel_w - 8
        panel_y = screen_y + 8

        # Background panel
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((20, 20, 30, 200))
        self.screen.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(
            self.screen, (150, 150, 150), (panel_x, panel_y, panel_w, panel_h), 2
        )

        # "MAP" label
        label = self.font_ui_xs.render("MAP", True, (180, 180, 180))
        self.screen.blit(
            label, (panel_x + panel_w // 2 - label.get_width() // 2, panel_y + 3)
        )

        grid_top = panel_y + 14 + 4  # below label

        for row in range(WINDOW):
            for col in range(WINDOW):
                sx = cx + (col - half)
                sy = cy + (row - half)

                cell_x = panel_x + 4 + col * (CELL + GAP)
                cell_y = grid_top + row * (CELL + GAP)

                if (sx, sy) in self.visited_sectors:
                    if (sx, sy) in self.land_sectors:
                        biome = get_sector_biome(self.world_seed, sx, sy)
                        color = {
                            BiomeType.STANDARD: (50, 110, 50),
                            BiomeType.TUNDRA: (120, 180, 220),
                            BiomeType.VOLCANO: (200, 70, 20),
                            BiomeType.ZOMBIE: (80, 95, 60),
                            BiomeType.DESERT: (195, 170, 85),
                        }.get(biome, (50, 110, 50))
                    else:
                        color = (35, 55, 110)  # visited ocean — dark navy
                elif (sx, sy) in self.sky_revealed_sectors:
                    # Seen from sky but never visited on foot — lighter fog tint
                    if (sx, sy) in self.land_sectors:
                        color = (30, 65, 30)   # dim green land
                    else:
                        color = (20, 30, 60)   # dim ocean
                else:
                    color = (25, 25, 35)  # fog / unvisited

                pygame.draw.rect(self.screen, color, (cell_x, cell_y, CELL, CELL))

                # Sky-revealed (but not foot-visited) land cells get a sky-blue tint border
                if (sx, sy) in self.sky_revealed_sectors and (sx, sy) not in self.visited_sectors:
                    pygame.draw.rect(self.screen, (60, 100, 160), (cell_x, cell_y, CELL, CELL), 1)

                # Highlight current sector with a bright border
                if sx == cx and sy == cy:
                    pygame.draw.rect(
                        self.screen, (220, 220, 255), (cell_x, cell_y, CELL, CELL), 2
                    )

        # Draw a small dot at the exact centre cell to mark the player
        centre_col = half
        centre_row = half
        dot_x = panel_x + 4 + centre_col * (CELL + GAP) + CELL // 2
        dot_y = grid_top + centre_row * (CELL + GAP) + CELL // 2
        pygame.draw.circle(self.screen, (255, 255, 255), (dot_x, dot_y), 2)

    # ------------------------------------------------------------------
    # World tile sprite rendering (SIGN / BROKEN_LADDER / SKY_LADDER)
    # ------------------------------------------------------------------

    # Maps tile ID → (sprite_name, frame_w, frame_h) for above-tile sprites
    _TILE_SPRITE_NAMES: dict[int, str] = {}   # populated lazily

    def _draw_world_tile_sprite(self, tid: int, sx: int, sy: int, ticks: int) -> None:
        """Draw a world-object sprite (sign, ladder) over the tile base rectangle.

        Ladders are 1-tile wide × 2-tiles tall so they are drawn offset upward.
        """
        from src.rendering.registry import SpriteRegistry
        from src.rendering.animator import AnimationState
        names = {
            SIGN:          ("sign",           32, 32),
            BROKEN_LADDER: ("broken_ladder",  32, 64),
            SKY_LADDER:    ("sky_ladder",     32, 64),
        }
        entry = names.get(tid)
        if entry is None:
            return
        sprite_name, draw_w, draw_h = entry
        data = SpriteRegistry.get_instance().get(sprite_name)
        if data is None:
            return
        sheet, manifest = data
        fw_raw, fh_raw = manifest["frame_size"]
        state_data = manifest["states"].get("idle")
        if state_data is None:
            return
        frame_surf = sheet.subsurface(pygame.Rect(0, state_data["row"] * fh_raw, fw_raw, fh_raw))
        scaled = pygame.transform.scale(frame_surf, (draw_w, draw_h))
        self.screen.blit(scaled, (sx, sy - (draw_h - 32)))

    # ------------------------------------------------------------------
    # Sign text popup
    # ------------------------------------------------------------------

    def _draw_sign_display(
        self,
        player: Player,
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        """Draw the sign text panel at the bottom of player's viewport if active."""
        pid = player.player_id
        disp = self._sign_display[pid]
        if disp is None:
            return

        lines = disp["text"].split("\n")
        font = self.font_ui_sm
        line_h = font.get_height() + 4
        padding = 14
        panel_h = line_h * len(lines) + padding * 2
        panel_w = view_w - 80
        panel_x = screen_x + 40
        panel_y = screen_y + view_h - panel_h - 24

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((15, 10, 5, 210))
        pygame.draw.rect(panel_surf, (180, 140, 70), (0, 0, panel_w, panel_h), 2, border_radius=4)
        self.screen.blit(panel_surf, (panel_x, panel_y))

        for i, line in enumerate(lines):
            color = (230, 200, 130) if i == 0 else (210, 185, 145)
            rendered = font.render(line, True, color)
            self.screen.blit(rendered, (panel_x + padding, panel_y + padding + i * line_h))

    # ------------------------------------------------------------------
    # Sky-view ascend/descend overlay
    # ------------------------------------------------------------------

    def _draw_sky_anim_overlay(
        self,
        player: Player,
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        """Draw the white flash overlay during ascend/descend animation."""
        pid = player.player_id
        anim = self._sky_anim[pid]
        if anim is None or anim["phase"] == "sky":
            return

        progress = anim["progress"]   # 0.0 → 1.0
        if anim["phase"] == "ascend":
            # Fade from transparent to white as we ascend
            alpha = int(progress * 255)
        else:  # descend
            alpha = int((1.0 - progress) * 255)

        if alpha <= 0:
            return
        overlay = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, alpha))
        self.screen.blit(overlay, (screen_x, screen_y))

    # ------------------------------------------------------------------
    # Sky view
    # ------------------------------------------------------------------

    def _draw_sky_view(
        self,
        player: Player,
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        """Render the full sky-view overlay for *player*."""
        pid = player.player_id

        # --- Sky gradient background ---
        for y in range(view_h):
            t = y / view_h
            r = int(30 + t * 70)
            g = int(60 + t * 100)
            b = int(120 + t * 100)
            pygame.draw.line(self.screen, (r, g, b),
                             (screen_x, screen_y + y), (screen_x + view_w, screen_y + y))

        # --- Sector grid ---
        player_sector = self._get_player_sector(player)
        cx, cy = player_sector if player_sector is not None else (0, 0)

        RADIUS = 5
        GRID = RADIUS * 2 + 1    # 11
        CELL_W, CELL_H = 68, 51  # px per sector cell
        GAP = 5
        total_w = GRID * (CELL_W + GAP) - GAP
        total_h = GRID * (CELL_H + GAP) - GAP
        grid_x0 = screen_x + (view_w - total_w) // 2
        grid_y0 = screen_y + (view_h - total_h) // 2

        for row in range(GRID):
            for col in range(GRID):
                sx_s = cx + (col - RADIUS)
                sy_s = cy + (row - RADIUS)
                cell_px = grid_x0 + col * (CELL_W + GAP)
                cell_py = grid_y0 + row * (CELL_H + GAP)
                cell_rect = pygame.Rect(cell_px, cell_py, CELL_W, CELL_H)

                revealed = (
                    (sx_s, sy_s) in self.visited_sectors
                    or (sx_s, sy_s) in self.sky_revealed_sectors
                )
                is_land = (sx_s, sy_s) in self.land_sectors

                if revealed and is_land:
                    thumb = self._generate_sector_thumbnail(sx_s, sy_s)
                    if thumb is not None:
                        scaled_thumb = pygame.transform.scale(thumb, (CELL_W, CELL_H))
                        self.screen.blit(scaled_thumb, (cell_px, cell_py))
                    else:
                        biome = get_sector_biome(self.world_seed, sx_s, sy_s)
                        bg_c = {
                            BiomeType.STANDARD: (50, 110, 50),
                            BiomeType.TUNDRA: (120, 180, 220),
                            BiomeType.VOLCANO: (200, 70, 20),
                            BiomeType.ZOMBIE: (80, 95, 60),
                            BiomeType.DESERT: (195, 170, 85),
                        }.get(biome, (50, 110, 50))
                        pygame.draw.rect(self.screen, bg_c, cell_rect)
                elif revealed:
                    pygame.draw.rect(self.screen, (35, 55, 110), cell_rect)
                else:
                    pygame.draw.rect(self.screen, (15, 15, 25), cell_rect)

                # Border
                border_c = (220, 220, 255) if (sx_s == cx and sy_s == cy) else (60, 70, 90)
                pygame.draw.rect(self.screen, border_c, cell_rect, 1 if (sx_s != cx or sy_s != cy) else 2)

        # --- Clouds ---
        self._draw_sky_clouds(screen_x, screen_y, view_w, view_h)

        # --- Header & footer ---
        header = self.font_dc_sm.render(
            f"Sky View  ·  Sector ({cx}, {cy})", True, (220, 235, 255)
        )
        self.screen.blit(header, (screen_x + view_w // 2 - header.get_width() // 2,
                                   screen_y + 14))

        interact_key = "E" if player.player_id == 1 else "5"
        footer = self.font_ui_sm.render(
            f"[{interact_key}] Descend", True, (180, 200, 230)
        )
        self.screen.blit(footer, (screen_x + view_w // 2 - footer.get_width() // 2,
                                   screen_y + view_h - 36))

        # --- Ascend/descend flash overlay on top ---
        anim = self._sky_anim[pid]
        if anim is not None and anim["phase"] != "sky":
            self._draw_sky_anim_overlay(player, screen_x, screen_y, view_w, view_h)

    def _draw_sky_clouds(
        self,
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        """Blit drifting translucent cloud sprites over the sky view."""
        from src.rendering.registry import SpriteRegistry
        data = SpriteRegistry.get_instance().get("cloud")
        if data is None:
            return
        sheet, manifest = data
        fw, fh = manifest["frame_size"]
        state_data = manifest["states"].get("idle", {})
        n_frames = state_data.get("frames", 4)

        for cloud in self._sky_clouds:
            frame_idx = int(cloud["frame"]) % n_frames
            frame_surf = sheet.subsurface(pygame.Rect(frame_idx * fw, 0, fw, fh)).copy()
            frame_surf.set_alpha(cloud["alpha"])
            cx = screen_x + int(cloud["x"]) % view_w
            cy = screen_y + int(cloud["y"]) % view_h
            self.screen.blit(frame_surf, (cx - fw // 2, cy - fh // 2))

    def _open_treasure_chest(self, player: Player, tx: int, ty: int) -> None:
        """Award loot from a treasure chest, spawn particles, and queue a reveal popup."""
        # Loot table: always a Sail + a random bonus
        loot = {"Sail": 1}
        bonus_pool = [
            {"Iron": random.randint(8, 18)},
            {"Gold": random.randint(4, 10)},
            {"Diamond": random.randint(1, 3)},
            {"Wood": random.randint(15, 30)},
            {"Stone": random.randint(20, 40)},
            {"Gold": random.randint(3, 7), "Iron": random.randint(5, 12)},
            {"Diamond": 1, "Gold": random.randint(3, 6)},
        ]
        bonus = random.choice(bonus_pool)
        for item, qty in bonus.items():
            loot[item] = loot.get(item, 0) + qty

        for item, qty in loot.items():
            player.inventory[item] = player.inventory.get(item, 0) + qty

        # Dramatic particle burst — gold/sparkle colours, upward fan + scatter
        sparkle_colors = [
            (255, 230, 80),  # gold
            (255, 200, 40),  # deep gold
            (255, 255, 160),  # pale yellow
            (255, 255, 255),  # white sparkle
            (255, 180, 60),  # amber
        ]
        for _ in range(55):
            p = Particle(tx, ty, random.choice(sparkle_colors), player.current_map)
            # Override default random speed with a stronger upward bias
            angle = random.uniform(-math.pi, 0)  # upper hemisphere
            speed = random.uniform(2, 6)
            p.vx = math.cos(angle) * speed
            p.vy = math.sin(angle) * speed
            p.life = random.randint(25, 50)
            p.size = random.randint(2, 5)
            self.particles.append(p)
        # A few stray downward particles for the "chest lid" effect
        for _ in range(12):
            p = Particle(tx, ty, (200, 140, 40), player.current_map)
            p.life = random.randint(10, 20)
            p.size = random.randint(3, 6)
            self.particles.append(p)

        # Queue reveal popup (lasts 180 ticks ≈ 3 s at 60 fps)
        self.treasure_reveals.append(
            {
                "player_id": player.player_id,
                "items": loot,
                "timer": 180.0,
            }
        )

    def _draw_treasure_reveal(
        self, player: Player, screen_x: int, screen_y: int, view_w: int, view_h: int
    ) -> None:
        """Draw the treasure chest loot popup for a player's viewport."""
        reveal = next(
            (r for r in self.treasure_reveals if r["player_id"] == player.player_id),
            None,
        )
        if reveal is None:
            return

        # Fade out during the last 60 ticks
        alpha = int(min(255, reveal["timer"] / 60 * 255))
        alpha = max(0, min(255, alpha))

        items = reveal["items"]
        item_count = len(items)

        panel_w = max(280, item_count * 90 + 40)
        panel_h = 100
        panel_x = screen_x + view_w // 2 - panel_w // 2
        panel_y = screen_y + view_h // 2 - panel_h // 2 - 40

        # Background panel
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((30, 20, 0, min(220, alpha)))
        self.screen.blit(panel_surf, (panel_x, panel_y))
        border_col = (220, 180, 40, alpha)
        border_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(border_surf, border_col, (0, 0, panel_w, panel_h), 3)
        self.screen.blit(border_surf, (panel_x, panel_y))

        # Header
        font_med = self.font_dc_med
        font_sm = self.font_dc_sm
        header = font_med.render("✦ TREASURE! ✦", True, (255, 220, 60))
        header.set_alpha(alpha)
        self.screen.blit(
            header,
            (panel_x + panel_w // 2 - header.get_width() // 2, panel_y + 6),
        )

        # Loot items in a row
        item_y = panel_y + 52
        total_w = sum(font_sm.size(f"{k}  x{v}")[0] + 16 for k, v in items.items())
        ix = panel_x + panel_w // 2 - total_w // 2
        item_colors = {
            "Sail": (100, 200, 255),
            "Iron": (180, 200, 220),
            "Gold": (255, 215, 0),
            "Diamond": (180, 240, 255),
            "Wood": (180, 130, 70),
            "Stone": (160, 160, 160),
        }
        for item, qty in items.items():
            col = item_colors.get(item, (220, 220, 220))
            txt = font_sm.render(f"{item}  x{qty}", True, col)
            txt.set_alpha(alpha)
            self.screen.blit(txt, (ix, item_y))
            ix += txt.get_width() + 16

    def _draw_craft_menu(
        self, player: Player, screen_x: int, screen_y: int, view_w: int, view_h: int
    ) -> None:
        """Draw the crafting menu overlay centered in the player's viewport."""
        cursor = self.craft_menus[player.player_id]
        if cursor is None:
            return

        font_sm = self.font_ui_sm
        font_xs = self.font_ui_xs

        # Filter recipes by housing tier
        current_map_obj = self.get_player_current_map(player)
        housing_tier = getattr(current_map_obj, "housing_tier", 0)
        available_recipes = [r for r in RECIPES if r.get("min_tier", 0) <= housing_tier]
        tier_name = SETTLEMENT_TIER_NAMES[housing_tier]

        row_h = 28
        total_entries = len(available_recipes) + 1  # recipes + Close
        panel_w = 280
        panel_h = 50 + total_entries * row_h + 14

        px = screen_x + (view_w - panel_w) // 2
        py = screen_y + (view_h - panel_h) // 2

        # Background panel
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((20, 20, 30, 220))
        self.screen.blit(panel_surf, (px, py))
        pygame.draw.rect(self.screen, (150, 150, 200), (px, py, panel_w, panel_h), 2)

        # Title
        title = font_sm.render(
            f"Crafting [{tier_name}]  (E craft · Esc close)", True, (200, 200, 255)
        )
        self.screen.blit(title, (px + 10, py + 10))
        pygame.draw.line(
            self.screen,
            (80, 80, 120),
            (px + 6, py + 32),
            (px + panel_w - 6, py + 32),
            1,
        )

        # Recipe rows
        for idx, recipe in enumerate(available_recipes):
            ry = py + 40 + idx * row_h
            if idx == cursor:
                pygame.draw.rect(
                    self.screen, (60, 80, 140), (px + 4, ry, panel_w - 8, row_h - 2)
                )
            name_surf = font_sm.render(recipe["name"], True, (230, 230, 230))
            self.screen.blit(name_surf, (px + 10, ry + 4))

            # Cost shown as colored "have/need" pairs
            cx = px + 140
            for item, needed in recipe["cost"].items():
                have = player.inventory.get(item, 0)
                met = have >= needed
                color = (100, 255, 100) if met else (255, 100, 100)
                cost_surf = font_xs.render(f"{item}: {have}/{needed}", True, color)
                self.screen.blit(cost_surf, (cx, ry + 8))
                cx += cost_surf.get_width() + 8

        # Close row
        close_idx = len(available_recipes)
        ry = py + 40 + close_idx * row_h
        if close_idx == cursor:
            pygame.draw.rect(
                self.screen, (60, 80, 140), (px + 4, ry, panel_w - 8, row_h - 2)
            )
        close_surf = font_sm.render("Close", True, (180, 180, 180))
        self.screen.blit(close_surf, (px + 10, ry + 4))

    # -- Equipment menu helpers -------------------------------------------

    def _equip_menu_options(self, player: Player, slot_key: str) -> list[str]:
        """Return the list of option identifiers for the equipment sub-menu.

        Includes compatible items from inventory, '_unequip' if something is
        currently equipped, and '_back' to cancel.
        """
        options: list[str] = []
        for item_name in sorted(player.inventory):
            if item_fits_slot(item_name, slot_key) and player.inventory[item_name] > 0:
                options.append(item_name)
        if player.equipment.get(slot_key) is not None:
            options.append("_unequip")
        options.append("_back")
        return options

    def _draw_equip_menu(
        self, player: Player, screen_x: int, screen_y: int, view_w: int, view_h: int
    ) -> None:
        """Draw the equipment + inventory menu overlay centered in the player's viewport."""
        state = self.equip_menus[player.player_id]
        if state is None:
            return

        font_sm = self.font_ui_sm
        font_xs = self.font_ui_xs

        row_h = 26
        num_slots = len(ARMOR_SLOT_ORDER)

        # Left pane: equipment slots; right pane: inventory list
        equip_w = 320
        inv_w = 220
        gap = 8
        panel_w = equip_w + gap + inv_w
        panel_h = max(50 + num_slots * row_h + 14, 300)

        px = screen_x + (view_w - panel_w) // 2
        py = screen_y + (view_h - panel_h) // 2

        # Background panel
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((20, 20, 30, 220))
        self.screen.blit(panel_surf, (px, py))
        pygame.draw.rect(self.screen, (150, 130, 200), (px, py, panel_w, panel_h), 2)

        # Divider between panes
        div_x = px + equip_w + gap // 2
        pygame.draw.line(
            self.screen, (80, 70, 120), (div_x, py + 6), (div_x, py + panel_h - 6), 1
        )

        # --- Left pane: Equipment ---
        title = font_sm.render(
            f"Equipment  ({pygame.key.name(player.controls.equip_key).upper()} close)",
            True,
            (200, 180, 255),
        )
        self.screen.blit(title, (px + 10, py + 10))

        def_pct = int(player.defense_pct * 100)
        def_surf = font_xs.render(f"Defense: {def_pct}%", True, (160, 220, 160))
        self.screen.blit(def_surf, (px + equip_w - def_surf.get_width() - 10, py + 12))

        pygame.draw.line(
            self.screen,
            (80, 70, 120),
            (px + 6, py + 32),
            (px + equip_w - 6, py + 32),
            1,
        )

        slot_idx = state["slot_idx"]
        sub_idx = state["sub_idx"]

        for idx, slot_key in enumerate(ARMOR_SLOT_ORDER):
            ry = py + 40 + idx * row_h
            is_selected = idx == slot_idx and sub_idx is None

            if is_selected:
                pygame.draw.rect(
                    self.screen, (60, 50, 120), (px + 4, ry, equip_w - 8, row_h - 2)
                )

            label = SLOT_LABELS[slot_key]
            equipped = player.equipment.get(slot_key)

            label_surf = font_sm.render(label, True, (200, 200, 200))
            self.screen.blit(label_surf, (px + 10, ry + 4))

            if equipped:
                if equipped in ARMOR_PIECES:
                    swatch_color = ARMOR_PIECES[equipped]["color"]
                elif equipped in ACCESSORY_PIECES:
                    swatch_color = ACCESSORY_PIECES[equipped]["color"]
                else:
                    swatch_color = (120, 120, 120)

                pygame.draw.rect(
                    self.screen,
                    swatch_color,
                    (px + 100, ry + 5, 12, 12),
                    border_radius=2,
                )

                name_surf = font_xs.render(equipped, True, (230, 230, 230))
                self.screen.blit(name_surf, (px + 118, ry + 6))

                if equipped in ARMOR_PIECES:
                    dur = player.durability.get(equipped, 0)
                    max_dur = ARMOR_PIECES[equipped]["durability"]
                    bar_w = 60
                    bar_x = px + equip_w - bar_w - 10
                    bar_y = ry + 8
                    pygame.draw.rect(
                        self.screen, (60, 60, 60), (bar_x, bar_y, bar_w, 8)
                    )
                    fill = int(bar_w * dur / max_dur) if max_dur else 0
                    bar_color = (
                        (80, 220, 80)
                        if dur > max_dur * 0.5
                        else (220, 180, 40) if dur > max_dur * 0.2 else (220, 60, 60)
                    )
                    if fill > 0:
                        pygame.draw.rect(
                            self.screen, bar_color, (bar_x, bar_y, fill, 8)
                        )
                    pygame.draw.rect(
                        self.screen, (120, 120, 120), (bar_x, bar_y, bar_w, 8), 1
                    )
                elif equipped in ACCESSORY_PIECES:
                    lbl = ACCESSORY_PIECES[equipped]["label"]
                    eff_surf = font_xs.render(lbl, True, (180, 255, 180))
                    self.screen.blit(
                        eff_surf, (px + equip_w - eff_surf.get_width() - 10, ry + 6)
                    )
            else:
                empty_surf = font_xs.render("—", True, (90, 90, 90))
                self.screen.blit(empty_surf, (px + 100, ry + 6))

        # --- Right pane: Inventory + Upgrades ---
        inv_px = px + equip_w + gap
        self.screen.blit(
            font_sm.render("Inventory", True, (200, 200, 255)), (inv_px + 6, py + 10)
        )
        pygame.draw.line(
            self.screen,
            (80, 70, 120),
            (inv_px + 4, py + 32),
            (inv_px + inv_w - 4, py + 32),
            1,
        )

        inv_items = sorted(
            ((k, v) for k, v in player.inventory.items() if v > 0),
            key=lambda kv: kv[0],
        )

        # Reserve space at the bottom for upgrades section (~80px)
        inv_bottom = py + panel_h - 88
        iy = py + 38
        for item_name, count in inv_items:
            if iy + 14 > inv_bottom:
                self.screen.blit(
                    font_xs.render("…", True, (150, 150, 150)), (inv_px + 6, iy)
                )
                break
            if item_name in ARMOR_PIECES:
                ic = ARMOR_PIECES[item_name]["color"]
            elif item_name in ACCESSORY_PIECES:
                ic = ACCESSORY_PIECES[item_name]["color"]
            else:
                ic = (180, 180, 180)
            pygame.draw.rect(
                self.screen, ic, (inv_px + 6, iy + 1, 8, 8), border_radius=1
            )
            self.screen.blit(
                font_xs.render(f"{item_name}: {count}", True, (220, 220, 220)),
                (inv_px + 18, iy),
            )
            iy += 16

        if not inv_items:
            self.screen.blit(
                font_xs.render("(empty)", True, (100, 100, 100)), (inv_px + 6, py + 40)
            )

        # Upgrades divider
        uy = py + panel_h - 84
        pygame.draw.line(
            self.screen, (80, 70, 120), (inv_px + 4, uy), (inv_px + inv_w - 4, uy), 1
        )
        self.screen.blit(
            font_xs.render("Upgrades", True, (200, 200, 200)), (inv_px + 6, uy + 4)
        )

        inv = player.inventory
        uy += 18
        # Pickaxe
        if player.pick_level < len(UPGRADE_COSTS):
            cost = UPGRADE_COSTS[player.pick_level]
            can = all(inv.get(k, 0) >= v for k, v in cost.items())
            cost_str = "  ".join(f"{k}:{inv.get(k,0)}/{v}" for k, v in cost.items())
            pick_col = (100, 255, 100) if can else (200, 100, 100)
            self.screen.blit(
                font_xs.render(f"[U] Pick: {cost_str}", True, pick_col),
                (inv_px + 6, uy),
            )
        else:
            self.screen.blit(
                font_xs.render("Pick: MAX", True, (255, 215, 0)), (inv_px + 6, uy)
            )
        uy += 14
        # Weapon
        if player.weapon_level < len(WEAPON_UNLOCK_COSTS):
            cost = WEAPON_UNLOCK_COSTS[player.weapon_level]
            can = all(inv.get(k, 0) >= v for k, v in cost.items())
            cost_str = "  ".join(f"{k}:{inv.get(k,0)}/{v}" for k, v in cost.items())
            wpn_col = (100, 255, 100) if can else (200, 100, 100)
            self.screen.blit(
                font_xs.render(f"[N] Wpn: {cost_str}", True, wpn_col), (inv_px + 6, uy)
            )
        else:
            self.screen.blit(
                font_xs.render("Weapon: MAX", True, (255, 215, 0)), (inv_px + 6, uy)
            )
        uy += 14
        # Build shortcuts
        dirt = inv.get("Dirt", 0)
        house_col = (100, 255, 100) if dirt >= HOUSE_BUILD_COST else (200, 100, 100)
        self.screen.blit(
            font_xs.render(
                f"[B] House: Dirt {dirt}/{HOUSE_BUILD_COST}", True, house_col
            ),
            (inv_px + 6, uy),
        )

        # Sub-menu overlay (drawn on top of both panes)
        if sub_idx is not None:
            slot_key = ARMOR_SLOT_ORDER[slot_idx]
            options = self._equip_menu_options(player, slot_key)

            sub_row_h = 24
            sub_w = 260
            sub_h = 16 + len(options) * sub_row_h
            sx = px + (panel_w - sub_w) // 2
            sy = py + (panel_h - sub_h) // 2

            sub_surf = pygame.Surface((sub_w, sub_h), pygame.SRCALPHA)
            sub_surf.fill((15, 15, 25, 240))
            self.screen.blit(sub_surf, (sx, sy))
            pygame.draw.rect(self.screen, (180, 140, 220), (sx, sy, sub_w, sub_h), 2)

            for oidx, opt in enumerate(options):
                oy = sy + 8 + oidx * sub_row_h
                if oidx == sub_idx:
                    pygame.draw.rect(
                        self.screen,
                        (80, 55, 140),
                        (sx + 4, oy, sub_w - 8, sub_row_h - 2),
                    )

                if opt == "_unequip":
                    opt_text = "Unequip"
                    opt_color = (255, 160, 100)
                elif opt == "_back":
                    opt_text = "Back"
                    opt_color = (160, 160, 160)
                else:
                    opt_text = opt
                    opt_color = (230, 230, 230)
                    if opt in ARMOR_PIECES:
                        c = ARMOR_PIECES[opt]["color"]
                    elif opt in ACCESSORY_PIECES:
                        c = ACCESSORY_PIECES[opt]["color"]
                    else:
                        c = (120, 120, 120)
                    pygame.draw.rect(
                        self.screen, c, (sx + 8, oy + 5, 10, 10), border_radius=2
                    )

                opt_surf = font_sm.render(opt_text, True, opt_color)
                self.screen.blit(opt_surf, (sx + 24, oy + 4))

    def _draw_death_challenge(
        self, player: Player, screen_x: int, screen_y: int, view_w: int, view_h: int
    ) -> None:
        """Draw the death/respawn math challenge overlay for a player's viewport."""
        challenge = self.death_challenges.get(player.player_id)
        if challenge is None:
            return

        # Semi-transparent dark overlay over the whole viewport
        overlay = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (screen_x, screen_y))

        font_big = self.font_dc_big
        font_med = self.font_dc_med
        font_small = self.font_dc_sm

        cx = screen_x + view_w // 2
        cy = screen_y + view_h // 2

        panel_w, panel_h = 360, 210
        panel_x = cx - panel_w // 2
        panel_y = cy - panel_h // 2

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((20, 10, 10, 235))
        self.screen.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(
            self.screen, (200, 50, 50), (panel_x, panel_y, panel_w, panel_h), 3
        )

        # "YOU DIED" header
        died_surf = font_big.render("YOU DIED", True, (255, 50, 50))
        self.screen.blit(died_surf, (cx - died_surf.get_width() // 2, panel_y + 14))

        # Instruction
        desc_surf = font_small.render(
            "Solve to respawn at full health:", True, (200, 200, 200)
        )
        self.screen.blit(desc_surf, (cx - desc_surf.get_width() // 2, panel_y + 62))

        # Math question
        q_surf = font_med.render(challenge["question"], True, (255, 255, 100))
        self.screen.blit(q_surf, (cx - q_surf.get_width() // 2, panel_y + 88))

        # Answer input field
        input_display = challenge["input"] if challenge["input"] else "_"
        input_color = (255, 80, 80) if challenge.get("wrong") else (100, 255, 100)
        input_surf = font_med.render(input_display, True, input_color)
        self.screen.blit(input_surf, (cx - input_surf.get_width() // 2, panel_y + 130))

        # Hint / wrong-answer message
        if challenge.get("wrong"):
            hint_surf = font_small.render(
                "Wrong answer — try again!", True, (255, 80, 80)
            )
        else:
            hint_surf = font_small.render(
                "Type your answer and press Enter", True, (140, 140, 140)
            )
        self.screen.blit(hint_surf, (cx - hint_surf.get_width() // 2, panel_y + 175))
