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
    AccessoryEffect,
    ArmorMaterial,
)
from src.data.attack_patterns import (
    AttackPattern,
    WEAPON_REGISTRY,
)
from src.entities.attacks import create_attack
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
from src.world.generation import finalize_scene
from src.world.environments import (
    CaveEnvironment,
    UnderwaterEnvironment,
    PortalRealmEnvironment,
    HousingEnvironment,
    OverlandEnvironment,
)
from src.entities import (
    Player,
    Projectile,
    Worker,
    Pet,
    Enemy,
    Creature,
)
from src.entities.attack import Attack
from src.entities.player import CONTROL_SCHEME_PLAYER1, CONTROL_SCHEME_PLAYER2
from src.effects import Particle, FloatingText
from src.save import save_game, load_game, apply_save
from src.ui.death_challenge import DeathChallengeManager
from src.ui.treasure import TreasureManager
from src.ui.player_hud import PlayerHUD
from src.ui.inventory import (
    InventoryState,
    InventoryTab,
)
from src.ui.inventory_renderer import InventoryRenderer
from src.world.sector_manager import SectorManager
from src.world.portal_manager import PortalManager


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

        _sprites_dir = _os.path.join(
            _os.path.dirname(_os.path.dirname(__file__)), "assets", "sprites"
        )
        SpriteRegistry.get_instance().load_all(_sprites_dir)

        # Load tile atlas sprite sheets
        from src.rendering.tile_registry import TileSpriteRegistry

        _tiles_dir = _os.path.join(
            _os.path.dirname(_os.path.dirname(__file__)), "assets", "tiles"
        )
        TileSpriteRegistry.get_instance().load_all(_tiles_dir)

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
        world_data, objects_data = generate_world()
        overland_gmap = GameMap(world_data, tileset="overland")
        for r in range(overland_gmap.rows):
            for c in range(overland_gmap.cols):
                if objects_data[r][c] is not None:
                    overland_gmap.set_object(r, c, objects_data[r][c])
        # Seed enemies before wrapping so MapScene transfers them immediately.
        overland_gmap.enemies = spawn_enemies(overland_gmap.world)
        overland_scene = MapScene(overland_gmap)
        finalize_scene(overland_scene, GRASS)
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
            for search_dist in range(max(WORLD_COLS, WORLD_ROWS)):
                for dc in range(-search_dist, search_dist + 1):
                    for dr in range(-search_dist, search_dist + 1):
                        if abs(dc) != search_dist and abs(dr) != search_dist:
                            continue
                        col = start_col + dc
                        row = start_row + dr
                        if 0 <= col < WORLD_COLS and 0 <= row < WORLD_ROWS:
                            if overland_map.get_tile(row, col) == GRASS:
                                return col * TILE + TILE // 2, row * TILE + TILE // 2
            # Fallback to center if no walkable tile found
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
        # (owned by SectorManager, but referenced during __init__ for ordering)

        # Effect routers: self.floats.append(f) and self.particles.append(p) route
        # to the appropriate MapScene so all 60+ call-sites need not change.
        self.floats: _EffectRouter = _EffectRouter(self._add_float)
        self.particles: _EffectRouter = _EffectRouter(self._add_particle)

        self.running = True

        # Death challenge manager
        self.death_challenge = DeathChallengeManager(self)
        # Backward compat alias for save.py and other references
        self.death_challenges = self.death_challenge.challenges

        # Inventory overlay (rendering + input + state)
        self.inventory = InventoryRenderer(self)

        # Portal manager — owns portal quests, realm nav, warp animations
        self.portals = PortalManager(self)
        # Backward compat alias for save.py and rendering
        self.portal_quests = self.portals.portal_quests

        # Treasure chest reveal UI
        self.treasure = TreasureManager(self)
        # Backward compat alias
        self.treasure_reveals = self.treasure.reveals

        # Player viewport HUD
        self.player_hud = PlayerHUD(self)

        # Sector manager — owns seed, visited/land/sky_revealed sets, entity archive,
        # biome warn timers, sector wipe state, thumbnail cache
        _seed = random.randint(0, 0xFFFF_FFFF)
        self.sectors = SectorManager(self, _seed)
        # Alias sector (0,0) as the home overland map so sector logic can use one key type
        self.maps[("sector", 0, 0)] = self.maps["overland"]
        # Backward compat aliases for save.py
        self.world_seed = self.sectors.world_seed
        self.visited_sectors = self.sectors.visited_sectors
        self.land_sectors = self.sectors.land_sectors
        self.sky_revealed_sectors = self.sectors.sky_revealed_sectors
        self._entity_archive = self.sectors._entity_archive
        self._sector_thumbnail_cache = self.sectors._sector_thumbnail_cache
        self._biome_warn_timers = self.sectors._biome_warn_timers
        self.sector_wipe = self.sectors.sector_wipe

        # Backward compat alias for portal warp state
        self.portal_warp = self.portals.portal_warp
        # Portal lava hurt cooldown: {player_id: int} (frames until next lava damage tick)
        self._lava_hurt_timers: dict[int, int] = {1: 0, 2: 0}
        # Mount state: which Creature each player is currently riding (None = none)
        self._player_mounts: dict[int, Creature | None] = {1: None, 2: None}

        # Sky-ladder quest state
        self._sky_view: dict[int, bool] = {1: False, 2: False}
        # phase: "ascend" | "sky" | "descend" | None; progress: 0.0 → 1.0 (ticks)
        self._sky_anim: dict[int, dict | None] = {1: None, 2: None}
        self._sky_clouds: list[dict] = []
        # Per-player sign text popup: {text: str, timer: float (seconds)}
        self._sign_display: dict[int, dict | None] = {1: None, 2: None}
        # Exit confirmation dialog
        self._confirm_quit: bool = False
        # Debug: draw enemy hitboxes
        self._debug_hitboxes: bool = False

        # Load saved state if a save file exists
        save_data = load_game()
        if save_data is not None:
            apply_save(self, save_data)

        # Place/verify portal ruins on the overland map (skip if loaded from save)
        if "overland" not in self.portal_quests:
            self.portals.assign_portal_quest("overland")
            self.portals.place_portal_on_map(self.maps["overland"], "overland")

        # Place broken ladder + sign on the overland map (new game only)
        if save_data is None:
            self.portals.place_sky_ladder_quest(self.maps["overland"])

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
        if self._sky_anim[pid] is not None:
            return  # already animating
        # Don't switch to sky yet — animate over the world first
        self._sky_anim[pid] = {"phase": "ascend_out", "progress": 0.0}
        self.sectors.reveal_sky_sectors(player)
        if not self._sky_clouds:
            self._init_sky_clouds()

    def _exit_sky_view(self, player: Player) -> None:
        """Begin the descend animation for *player*, closing the sky view."""
        pid = player.player_id
        anim = self._sky_anim[pid]
        if anim is not None and anim["phase"] == "sky":
            # Animate over sky first, then switch to world at the peak
            self._sky_anim[pid] = {"phase": "descend_out", "progress": 0.0}
        else:
            # Already animating — skip straight to closed
            self._sky_view[pid] = False
            self._sky_anim[pid] = None

    def _init_sky_clouds(self) -> None:
        """Populate the cloud layer with 8 randomly positioned cloud instances."""
        self._sky_clouds = []
        from src.rendering.registry import SpriteRegistry

        reg = SpriteRegistry.get_instance()
        cloud_entry = reg.get("cloud")
        n_frames = cloud_entry[1]["states"]["idle"]["frames"] if cloud_entry else 4
        for i in range(8):
            self._sky_clouds.append(
                {
                    "x": float(random.randint(0, 1920)),
                    "y": float(random.randint(50, 900)),
                    "speed": random.uniform(0.15, 0.45),
                    "alpha": random.randint(70, 130),
                    "frame": random.randint(0, n_frames - 1),
                    "frame_timer": random.uniform(0.0, 2000.0),
                }
            )

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

    @property
    def paused(self) -> bool:
        """True when the game should be fully frozen (death challenge or exit confirmation)."""
        return self.death_challenge.has_active() or self._confirm_quit

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
                if self._confirm_quit:
                    self.running = False
                else:
                    self._confirm_quit = True
            elif event.type == pygame.KEYDOWN:
                if self._confirm_quit:
                    if event.key in (pygame.K_y, pygame.K_RETURN):
                        self.running = False
                    elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                        self._confirm_quit = False
                else:
                    self._handle_keydown(event.key)
            elif event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)

    def _handle_keydown(self, key: int) -> None:
        """Handle key press (for both players based on key)."""
        # --- Death challenge input (either player can type; blocks all other keys) ---
        active_pid = self.death_challenge.get_active_player_id()
        if active_pid is not None:
            active_player = (
                self.player1 if active_pid == self.player1.player_id else self.player2
            )
            if self.death_challenge.handle_keydown(key, active_player):
                return
            # While a death challenge is active, block everything else
            return

        # --- Inventory overlay input (takes priority over normal keys while open) ---
        inv_consumed = False
        for player in (self.player1, self.player2):
            pid = player.player_id
            if not self.inventory.is_open(pid):
                continue
            self.inventory.handle_input(key, player)
            inv_consumed = True
        if inv_consumed:
            return

        if key == pygame.K_ESCAPE:
            self._confirm_quit = True
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
        # DEBUG: F10 toggles enemy hitbox visualisation
        elif key == pygame.K_F10:
            self._debug_hitboxes = not self._debug_hitboxes
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
            self.inventory.toggle(self.player1.player_id)
        elif not self.player1.is_dead and key == self.player1.controls.cycle_weapon_key:
            self.player1.cycle_weapon()
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
            self.inventory.toggle(self.player2.player_id)
        elif not self.player2.is_dead and key == self.player2.controls.cycle_weapon_key:
            self.player2.cycle_weapon()

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
                        Worker(
                            tile_cx, tile_cy, player_id=player.player_id, home_map=home
                        )
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

        # Block interaction during sky-view animation
        if self._sky_anim[pid] is not None and self._sky_anim[pid]["phase"] != "sky":
            return

        # 3.6 Sky-view exit — takes priority over everything else
        if self._sky_view[pid]:
            self._exit_sky_view(player)
            return

        # Dismiss active sign display on interact press
        if self._sign_display[pid] is not None:
            self._sign_display[pid] = None
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
                    self.inventory.open_to_tab(player.player_id, InventoryTab.RECIPES)
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
                    _cave_scene = MapScene(env.generate())
                    finalize_scene(_cave_scene, GRASS)
                    self.maps[cave_key] = _cave_scene
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
                    int(player.x),
                    int(player.y) - 30,
                    "Dismounted!",
                    (180, 220, 100),
                    player.current_map,
                )
            )
            return
        # Check for a nearby unmounted creature on the same map
        mount_range = TILE * 1.5
        player_scene = self.maps.get(player.current_map)
        for c in player_scene.creatures if player_scene is not None else []:
            if c.rider_id is not None:
                continue
            if not c.mountable:
                continue
            dist = math.hypot(c.x - player.x, c.y - player.y)
            if dist <= mount_range:
                self._mount_player(player, c)
                self.floats.append(
                    FloatingText(
                        int(player.x),
                        int(player.y) - 30,
                        "Mounted!",
                        (100, 220, 180),
                        player.current_map,
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
                self.treasure.open_chest(player, tx, ty)
                return

        # 4.4 Adjacent SIGN — read its text
        if current_map_obj.tileset == "overland":
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == SIGN:
                    raw = object.__getattribute__(current_map_obj, "map")
                    text = raw.sign_texts.get((cc, rr), "...")
                    self._sign_display[pid] = {
                        "text": text,
                        "timer": 6.0,
                        "tile_col": cc,
                        "tile_row": rr,
                    }
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
                        self.floats.append(
                            FloatingText(
                                tx,
                                ty - 36,
                                "Ladder repaired!",
                                (120, 220, 80),
                                player.current_map,
                            )
                        )
                        for _ in range(14):
                            self.particles.append(
                                Particle(tx, ty, (200, 180, 80), player.current_map)
                            )
                    else:
                        needs = ", ".join(
                            f"{qty} {item}"
                            for item, qty in self._SKY_LADDER_COST.items()
                        )
                        self.floats.append(
                            FloatingText(
                                tx,
                                ty - 30,
                                f"Need: {needs}",
                                (255, 120, 80),
                                player.current_map,
                            )
                        )
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
                    self.portals.try_activate_ritual_stone(
                        player, current_map_obj, cc, rr
                    )
                    return

        # 4.6. Adjacent PORTAL_RUINS — show quest status or gather delivery
        if current_map_obj.tileset == "overland":
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == PORTAL_RUINS:
                    self.portals.try_interact_portal_ruins(player, player.current_map)
                    return

        # 4.7. Adjacent PORTAL_ACTIVE on island — enter portal realm
        if current_map_obj.tileset == "overland":
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == PORTAL_ACTIVE:
                    self.portals.enter_portal_realm(player)
                    return

        # 4.8. PORTAL_ACTIVE tile inside portal realm — exit to linked island
        if player.current_map == "portal_realm":
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                cc, rr = p_col + dc, p_row + dr
                if current_map_obj.get_tile(rr, cc) == PORTAL_ACTIVE:
                    self.portals.exit_portal_realm(player, cc, rr)
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
            finalize_scene(dive_scene, SAND)
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
            _house_scene = MapScene(house_map)
            finalize_scene(_house_scene, WOOD_FLOOR)
            self.maps[house_key] = _house_scene
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
            _sub_scene = MapScene(sub_map)
            finalize_scene(_sub_scene, WOOD_FLOOR)
            self.maps[sub_key] = _sub_scene
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

        self.portals.debug_force_portal_on_map(map_key, game_map)
        self.portals.add_realm_portal(map_key)

        # Generate a nearby island and restore its portal too so the realm
        # has two portals and the player can traverse between them.
        origin_sx = (
            map_key[1] if isinstance(map_key, tuple) and len(map_key) == 3 else 0
        )
        origin_sy = (
            map_key[2] if isinstance(map_key, tuple) and len(map_key) == 3 else 0
        )
        self.portals.debug_ensure_nearby_island(origin_sx, origin_sy)

        self.floats.append(
            FloatingText(
                int(player.x),
                int(player.y) - 36,
                "[DEBUG] Portal + nearby island ready!",
                (160, 60, 220),
                player.current_map,
            )
        )

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
                workers_on_map = (
                    len(home_scene_s.workers) if home_scene_s is not None else 0
                )
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
        # Draw at 32×32 base scale into a buffer, then scale up to TILE×TILE.
        _TS = TILE // 32
        buf = pygame.Surface((32, 32), pygame.SRCALPHA)
        buf.fill((0, 0, 0, 0))
        self._draw_house_tile_32(buf, 0, 0, tier, n, s, e, w, ticks)
        if _TS > 1:
            buf = pygame.transform.scale(buf, (TILE, TILE))
        self.screen.blit(buf, (tx, ty))

    def _draw_house_tile_32(
        self,
        sc: pygame.Surface,
        tx: int,
        ty: int,
        tier: int,
        n: bool,
        s: bool,
        e: bool,
        w: bool,
        ticks: int,
    ) -> None:
        """Draw a house tile at 32×32 base scale into *sc*."""

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
            if p.current_map == map_key
            and not p.is_dead
            and self._sky_anim[p.player_id] is None
            and not self._sky_view[p.player_id]
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
                _cave_scene2 = MapScene(env.generate())
                finalize_scene(_cave_scene2, GRASS)
                self.maps[cave_key] = _cave_scene2

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

        # Full freeze while paused (death challenge or exit confirmation)
        if self.paused:
            return

        keys = pygame.key.get_pressed()
        mouse_buttons = pygame.mouse.get_pressed()

        # Get player maps
        map1 = self.get_player_current_map(self.player1)
        map2 = self.get_player_current_map(self.player2)

        # Update maps after potential transitions

        # -- Sector-wipe animation tick ------------------------------------
        self.sectors.tick_wipe(dt)
        # -- Portal-warp animation tick ------------------------------------
        self.portals.tick_warp(dt)
        # -- Sky-view animation tick ---------------------------------------
        _SKY_ANIM_DURATION = 120.0  # frames at dt=1 (≈2 s at 60 fps)
        for pid in (1, 2):
            anim = self._sky_anim[pid]
            if anim is None:
                continue
            anim["progress"] += dt / _SKY_ANIM_DURATION
            phase = anim["phase"]
            if phase == "ascend_out" and anim["progress"] >= 1.0:
                # Peak white — switch to sky view, then fade out
                self._sky_view[pid] = True
                anim["phase"] = "ascend_in"
                anim["progress"] = 0.0
            elif phase == "ascend_in" and anim["progress"] >= 1.0:
                anim["phase"] = "sky"
                anim["progress"] = 0.0
            elif phase == "descend_out" and anim["progress"] >= 1.0:
                # Peak white — switch to world view, then fade out
                self._sky_view[pid] = False
                anim["phase"] = "descend_in"
                anim["progress"] = 0.0
            elif phase == "descend_in" and anim["progress"] >= 1.0:
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
            self.sectors.check_sector_transitions(self.player1)
        if not self.player2.is_dead:
            self.sectors.check_sector_transitions(self.player2)
        # ----------------------------------------------------------------

        # -- Biome entry damage timer tick --------------------------------
        self.sectors.tick_biome_damage(dt)
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
            if cur_map.get_tile(
                pr, pc
            ) == PORTAL_LAVA and not self.sectors.has_ancient_armor(player):
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
                        self.death_challenge.start(player)
            else:
                self._lava_hurt_timers[pid] = 0
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

        # Player 1 movement & mining (skipped while dead or inventory open)
        if not self.player1.is_dead and not self.inventory.is_open(1):
            if self.player1.on_mount:
                # Drive the mounted creature with player input
                mount1 = self._player_mounts[1]
                if mount1 is not None:
                    cs1 = self.player1.controls.move_keys
                    dx1 = (keys[cs1["right"]] - keys[cs1["left"]]) * 1.0
                    dy1 = (keys[cs1["down"]] - keys[cs1["up"]]) * 1.0
                    mount1.update_riding(dx1, dy1, dt, map1.world, self.player1.speed)
                    self.player1.x = mount1.x
                    self.player1.y = mount1.y
            else:
                p1_speed_mult = 1.0 + self.player1.active_effects().get(
                    AccessoryEffect.SPEED_BOOST, 0.0
                )
                base_speed1 = self.player1.speed
                self.player1.speed = base_speed1 * p1_speed_mult
                self.player1.update_movement(
                    keys, dt, map1.world, world_objects=list(map1.world_objects)
                )
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
                game_map=map1.map,
                scene=map1,
            )
        if not self.player1.is_dead:
            if self.player1.hurt_timer > 0:
                self.player1.hurt_timer -= dt

        # Player 2 movement & mining (skipped while dead or inventory open)
        if not self.player2.is_dead and not self.inventory.is_open(2):
            if self.player2.on_mount:
                # Drive the mounted creature with player input
                mount2 = self._player_mounts[2]
                if mount2 is not None:
                    cs2 = self.player2.controls.move_keys
                    dx2 = (keys[cs2["right"]] - keys[cs2["left"]]) * 1.0
                    dy2 = (keys[cs2["down"]] - keys[cs2["up"]]) * 1.0
                    mount2.update_riding(dx2, dy2, dt, map2.world, self.player2.speed)
                    self.player2.x = mount2.x
                    self.player2.y = mount2.y
            else:
                p2_speed_mult = 1.0 + self.player2.active_effects().get(
                    AccessoryEffect.SPEED_BOOST, 0.0
                )
                base_speed2 = self.player2.speed
                self.player2.speed = base_speed2 * p2_speed_mult
                self.player2.update_movement(
                    keys, dt, map2.world, world_objects=list(map2.world_objects)
                )
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
                game_map=map2.map,
                scene=map2,
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
            self.player1.check_level_up(
                scene1.particles, scene1.floats, self.player1.current_map
            )
        scene2 = self.maps.get(self.player2.current_map)
        if scene2 is not None:
            self.player2.check_level_up(
                scene2.particles, scene2.floats, self.player2.current_map
            )

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
        self.treasure.tick(dt)

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
            p.current_map for p in (self.player1, self.player2) if not p.is_dead
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
                        self.death_challenge.start(target_player)
            dead = [e for e in scene.enemies if e.hp <= 0]
            scene.enemies = [e for e in scene.enemies if e.hp > 0]
            for dead_e in dead:
                if dead_e.type_key == "stone_sentinel":
                    self.portals.on_sentinel_defeated(map_key)

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

    def _update_combat(
        self,
        keys: pygame.key.ScancodeWrapper,
        mouse_buttons: tuple[bool, bool, bool],
        dt: float,
    ) -> None:
        """Handle weapon firing for both players."""
        for player in (self.player1, self.player2):
            if player.weapon_cooldown > 0:
                player.weapon_cooldown -= dt
            if player.is_dead:
                continue

            if player.player_id == 1:
                fire_input = (
                    keys[player.controls.fire_key]
                    or mouse_buttons[2]
                    or player.auto_fire
                )
            else:
                fire_input = keys[player.controls.fire_key] or player.auto_fire

            # Beam management: keep existing beam alive while fire held
            scene = self.maps.get(player.current_map)
            if scene is not None:
                active_beam = self._find_active_beam(scene, player.player_id)
                if active_beam is not None:
                    if fire_input:
                        # Update beam direction to current facing
                        active_beam.dir_x = player.facing_dx
                        active_beam.dir_y = player.facing_dy
                        continue  # Don't spawn a new attack while beam is active
                    else:
                        active_beam.alive = False

            if fire_input and player.weapon_cooldown <= 0:
                wpn_def = WEAPON_REGISTRY.get(player.weapon_id)
                if wpn_def is None:
                    continue
                dmg_mult = 1.0 + player.active_effects().get(
                    AccessoryEffect.DAMAGE_BOOST, 0.0
                )
                atk = create_attack(
                    weapon=wpn_def,
                    x=player.x,
                    y=player.y,
                    dir_x=player.facing_dx,
                    dir_y=player.facing_dy,
                    player_id=player.player_id,
                    map_key=player.current_map,
                    damage_mult=dmg_mult,
                )
                if scene is not None:
                    scene.projectiles.append(atk)
                player.weapon_cooldown = wpn_def.cooldown

    @staticmethod
    def _find_active_beam(scene: MapScene, player_id: int) -> Attack | None:
        """Return the active BeamAttack for a player, or None."""
        from src.entities.attacks.beam import BeamAttack

        for atk in scene.projectiles:
            if isinstance(atk, BeamAttack) and atk.alive and atk.player_id == player_id:
                return atk
        return None

    def _update_projectiles(self, dt: float) -> None:
        """Update all attacks per-scene and check for hits."""
        for scene in self.maps.values():
            spawn_queue: list[Attack] = []
            for atk in scene.projectiles:
                # Determine which player owns this attack for player_x/y
                if atk.player_id == 1:
                    px, py = self.player1.x, self.player1.y
                else:
                    px, py = self.player2.x, self.player2.y
                atk.update(dt, px, py, scene.world)
                if atk.alive:
                    atk.check_hits(scene.enemies, scene.particles, scene.floats)
                # Spawn on-death attacks (e.g. bomb → explosion)
                if (
                    not atk.alive
                    and hasattr(atk, "weapon")
                    and atk.weapon.on_death_spawn
                ):
                    child_def = WEAPON_REGISTRY.get(atk.weapon.on_death_spawn)
                    if child_def is not None:
                        child = create_attack(
                            weapon=child_def,
                            x=atk.x,
                            y=atk.y,
                            dir_x=atk.dir_x,
                            dir_y=atk.dir_y,
                            player_id=atk.player_id,
                            map_key=atk.map_key,
                        )
                        spawn_queue.append(child)
                # Award XP
                if atk.player_id == 1:
                    xp_mult = 1.0 + self.player1.active_effects().get(
                        AccessoryEffect.XP_BOOST, 0.0
                    )
                    self.player1.xp += int(atk.xp_earned * xp_mult)
                elif atk.player_id == 2:
                    xp_mult = 1.0 + self.player2.active_effects().get(
                        AccessoryEffect.XP_BOOST, 0.0
                    )
                    self.player2.xp += int(atk.xp_earned * xp_mult)
                atk.xp_earned = 0
            scene.projectiles = [a for a in scene.projectiles if a.alive]
            scene.projectiles.extend(spawn_queue)

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

        # Death challenge overlay (full-screen, centered)
        active_pid = self.death_challenge.get_active_player_id()
        if active_pid is not None:
            active_player = (
                self.player1
                if active_pid == self.player1.player_id
                else self.player2
            )
            self.death_challenge.draw(
                active_player, 0, 0, screen_width, screen_height
            )

        # Exit confirmation overlay
        if self._confirm_quit:
            overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self.screen.blit(overlay, (0, 0))
            big_font = pygame.font.SysFont(None, 48)
            small_font = pygame.font.SysFont(None, 32)
            prompt = big_font.render(
                "Are you sure you want to exit?", True, (255, 255, 255)
            )
            hint = small_font.render(
                "Y / Enter = Quit      N / Esc = Cancel", True, (200, 200, 200)
            )
            cx = screen_width // 2
            cy = screen_height // 2
            self.screen.blit(prompt, (cx - prompt.get_width() // 2, cy - 30))
            self.screen.blit(hint, (cx - hint.get_width() // 2, cy + 20))

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

        from src.rendering.tile_registry import (
            TileSpriteRegistry as _TileReg,
            TILE_ID_TO_NAME as _TID2N,
            STANDALONE_TILE_IDS as _STANDALONE_IDS,
            compute_adjacency as _compute_adj,
            compute_scene_object_adjacency as _cso_adj,
        )

        _tile_reg = _TileReg.get_instance()
        _tileset = current_map.tileset

        for r in range(start_row, end_row):
            for c in range(start_col, end_col):
                tid = current_map.get_tile(r, c)
                if tid is None:
                    continue

                sx = c * TILE - int(cam_x) + screen_x
                sy = r * TILE - int(cam_y) + screen_y

                tile_name = _TID2N.get(tid)

                # --- Standalone tiles (sign, ladders) ---
                if tid in _STANDALONE_IDS and tile_name is not None:
                    # Draw base color rect first
                    tile_color = current_map.get_tileset_color(tid)
                    pygame.draw.rect(self.screen, tile_color, (sx, sy, TILE, TILE))
                    fps = _tile_reg.get_standalone_fps(tile_name)
                    fidx = int(ticks * fps / 1000.0) if fps > 0 else 0
                    result = _tile_reg.get_standalone(tile_name, fidx, _tileset)
                    if result is not None:
                        frame_surf, (dx, dy) = result
                        self.screen.blit(frame_surf, (sx + dx, sy + dy))
                    continue

                # --- Atlas tiles ---
                if tile_name is not None:
                    adj = _compute_adj(current_map, r, c, tid)
                    fps = _tile_reg.get_fps(tile_name)
                    if fps > 0:
                        fidx = int(ticks * fps / 1000.0) % 4
                    else:
                        tile_info = TILE_INFO.get(tid)
                        if (
                            tile_info
                            and tile_info.get("mineable")
                            and tile_info["hp"] > 0
                        ):
                            cur_hp = current_map.tile_hp[r][c]
                            max_hp = tile_info["hp"]
                            damage_pct = 1.0 - cur_hp / max_hp
                            fidx = min(3, int(damage_pct * 4))
                        else:
                            fidx = 0
                    frame = _tile_reg.get_frame(tile_name, adj, fidx, _tileset)
                    if frame is not None:
                        self.screen.blit(frame, (sx, sy))
                        # ANCIENT_STONE: pulse overlay if next ritual target
                        if tid == ANCIENT_STONE:
                            quest = self.portal_quests.get(player.current_map)
                            if (
                                quest
                                and quest["type"] == PortalQuestType.RITUAL
                                and not quest["restored"]
                            ):
                                positions = getattr(
                                    current_map, "ritual_stone_positions", []
                                )
                                next_idx = quest["stones_activated"]
                                if next_idx < len(positions) and positions[
                                    next_idx
                                ] == (c, r):
                                    S = TILE // 32
                                    pulse_y = int(math.sin(ticks * 0.01) * 3 * S)
                                    pygame.draw.polygon(
                                        self.screen,
                                        (240, 210, 50),
                                        [
                                            (sx + 10 * S, sy + 11 * S + pulse_y),
                                            (sx + 22 * S, sy + 11 * S + pulse_y),
                                            (sx + 16 * S, sy + 5 * S + pulse_y),
                                        ],
                                        2,
                                    )
                        continue

                # --- Fallback: flat colored rect ---
                tile_color = current_map.get_tileset_color(tid)
                pygame.draw.rect(self.screen, tile_color, (sx, sy, TILE, TILE))
        # Draw WorldObjects (mineables, interactables, transition tiles)
        for obj in current_map.objects_in_viewport(cam_x, cam_y, view_w, view_h):
            tile_name = _TID2N.get(obj.tile_id)
            if tile_name is None:
                continue
            osx = int(obj.x) - TILE // 2 - int(cam_x) + screen_x
            osy = int(obj.y) - TILE // 2 - int(cam_y) + screen_y
            if obj.tile_id in _STANDALONE_IDS:
                tile_color = current_map.get_tileset_color(obj.tile_id)
                pygame.draw.rect(self.screen, tile_color, (osx, osy, TILE, TILE))
                fps = _tile_reg.get_standalone_fps(tile_name)
                fidx = int(ticks * fps / 1000.0) if fps > 0 else 0
                result = _tile_reg.get_standalone(tile_name, fidx, _tileset)
                if result is not None:
                    frame_surf, (dx, dy) = result
                    self.screen.blit(frame_surf, (osx + dx, osy + dy))
            else:
                from src.data import TILE_INFO as _TI

                info = _TI.get(obj.tile_id)
                if info and info.get("mineable") and info.get("hp", 0) > 0:
                    max_hp = info["hp"]
                    damage_pct = 1.0 - obj.hp / max_hp
                    fidx = min(3, int(damage_pct * 4))
                else:
                    fidx = 0
                adj = _cso_adj(current_map, obj.row, obj.col, obj.tile_id)
                frame = _tile_reg.get_frame(tile_name, adj, fidx, _tileset)
                if frame is not None:
                    self.screen.blit(frame, (osx, osy))
                else:
                    tile_color = current_map.get_tileset_color(obj.tile_id)
                    pygame.draw.rect(self.screen, tile_color, (osx, osy, TILE, TILE))
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
                sc.draw(
                    self.screen, cam_x - screen_x, cam_y - screen_y, ticks, rider_color
                )
            for enemy in scene.enemies:
                enemy.draw(self.screen, cam_x - screen_x, cam_y - screen_y)
            if self._debug_hitboxes:
                hitbox_surf = pygame.Surface(
                    (view_w, view_h), pygame.SRCALPHA
                )
                for enemy in scene.enemies:
                    if enemy.hp <= 0:
                        continue
                    ex = int(enemy.x - cam_x + screen_x)
                    ey = int(enemy.y - cam_y + screen_y)
                    lx = ex - screen_x
                    ly = ey - screen_y
                    # Hitbox body (green filled)
                    pygame.draw.circle(
                        hitbox_surf,
                        (50, 255, 50, 60),
                        (lx, ly),
                        enemy.hitbox_radius,
                    )
                    # Hitbox outline (green)
                    pygame.draw.circle(
                        hitbox_surf,
                        (50, 255, 50, 180),
                        (lx, ly),
                        enemy.hitbox_radius,
                        2,
                    )
                    # Attack range (red outline)
                    pygame.draw.circle(
                        hitbox_surf,
                        (255, 50, 50, 100),
                        (lx, ly),
                        enemy.hitbox_radius + 20,
                        2,
                    )
                    # Centre point (white)
                    pygame.draw.circle(
                        hitbox_surf,
                        (255, 255, 255, 200),
                        (lx, ly),
                        3,
                    )
                self.screen.blit(hitbox_surf, (screen_x, screen_y))
            for proj in scene.projectiles:
                proj.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

        # Draw players that share this map
        current_map_key = player.current_map
        for p in (self.player1, self.player2):
            if p.current_map == current_map_key:
                # Hide player while ascending to sky view (not during descent back)
                anim = self._sky_anim[p.player_id]
                if anim is not None and anim["phase"] in ("ascend_out", "ascend_in"):
                    continue
                p.draw(self.screen, cam_x - screen_x, cam_y - screen_y)

        self.player_hud.draw(player, screen_x, screen_y, view_w, view_h)
        self.treasure.draw(player, screen_x, screen_y, view_w, view_h)
        if self.inventory.is_open(player.player_id):
            self.inventory.draw(player, screen_x, screen_y, view_w, view_h)

        # Sector-wipe flash overlay (drawn last so it appears on top)
        wipe_state = self.sector_wipe.get(player.player_id)
        if wipe_state:
            self.sectors.draw_sector_wipe_viewport(
                screen_x, screen_y, view_w, view_h, wipe_state["progress"]
            )

        # Portal-warp vortex overlay (drawn on top of sector wipe)
        warp_state = self.portal_warp.get(player.player_id)
        if warp_state:
            self._draw_portal_warp_viewport(
                screen_x, screen_y, view_w, view_h, warp_state["progress"]
            )

        self.screen.set_clip(None)

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
            pygame.draw.line(
                self.screen,
                (r, g, b),
                (screen_x, screen_y + y),
                (screen_x + view_w, screen_y + y),
            )

        # --- Sector grid ---
        player_sector = self.sectors.get_player_sector(player)
        cx, cy = player_sector if player_sector is not None else (0, 0)

        RADIUS = 5
        GRID = RADIUS * 2 + 1  # 11
        CELL_W, CELL_H = 68, 51  # px per sector cell
        GAP = 0
        total_w = GRID * CELL_W
        total_h = GRID * CELL_H
        grid_x0 = screen_x + (view_w - total_w) // 2
        grid_y0 = screen_y + (view_h - total_h) // 2

        for row in range(GRID):
            for col in range(GRID):
                sx_s = cx + (col - RADIUS)
                sy_s = cy + (row - RADIUS)
                cell_px = grid_x0 + col * CELL_W
                cell_py = grid_y0 + row * CELL_H
                cell_rect = pygame.Rect(cell_px, cell_py, CELL_W, CELL_H)

                revealed = (sx_s, sy_s) in self.visited_sectors or (
                    sx_s,
                    sy_s,
                ) in self.sky_revealed_sectors
                is_land = (sx_s, sy_s) in self.land_sectors

                if revealed and is_land:
                    thumb = self.sectors.generate_sector_thumbnail(sx_s, sy_s)
                    if thumb is not None:
                        scaled_thumb = pygame.transform.smoothscale(
                            thumb, (CELL_W, CELL_H)
                        )
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
                    pygame.draw.rect(self.screen, (28, 100, 180), cell_rect)
                else:
                    pygame.draw.rect(self.screen, (15, 15, 25), cell_rect)

                # Highlight current sector only
                if sx_s == cx and sy_s == cy:
                    pygame.draw.rect(self.screen, (220, 220, 255), cell_rect, 2)

        # --- Clouds ---
        self._draw_sky_clouds(screen_x, screen_y, view_w, view_h)

        # --- Header & footer ---
        header = self.font_dc_sm.render(
            f"Sky View  ·  Sector ({cx}, {cy})", True, (220, 235, 255)
        )
        self.screen.blit(
            header, (screen_x + view_w // 2 - header.get_width() // 2, screen_y + 14)
        )

        interact_key = "E" if player.player_id == 1 else "5"
        footer = self.font_ui_sm.render(
            f"[{interact_key}] Descend", True, (180, 200, 230)
        )
        self.screen.blit(
            footer,
            (screen_x + view_w // 2 - footer.get_width() // 2, screen_y + view_h - 36),
        )

        # --- Ascend/descend flash overlay on top ---
        anim = self._sky_anim[pid]
        if anim is not None and anim["phase"] != "sky":
            self.player_hud._draw_sky_anim_overlay(
                player, screen_x, screen_y, view_w, view_h
            )

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
