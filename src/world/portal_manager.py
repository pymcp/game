"""Portal quest management — quest assignment, restoration, realm navigation.

Extracted from game.py.  Owns portal quest state, realm generation, and
enter/exit portal realm logic.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from src.config import (
    TILE,
    GRASS,
    PORTAL_RUINS,
    PORTAL_ACTIVE,
    ANCIENT_STONE,
    PORTAL_FLOOR,
    PORTAL_WALL,
    SIGN,
    BROKEN_LADDER,
    SKY_LADDER,
    PORTAL_WARP_DURATION,
    TREASURE_CHEST,
    MapType,
)
from src.data import PortalQuestType
from src.effects import FloatingText, Particle
from src.world.map import GameMap
from src.world.scene import MapScene
from src.world.generation import finalize_scene

if TYPE_CHECKING:
    from src.entities.player import Player


class PortalManager:
    """Manages portal quests, the portal realm, and portal warp animations.

    Owns:
    * ``portal_quests`` — map_key → quest dict
    * ``portal_warp`` — player_id → animation state dict
    """

    def __init__(self, game: object) -> None:
        self.game = game
        self.portal_quests: dict[str | tuple, dict] = {}
        self.portal_warp: dict[int, dict] = {}

    # ------------------------------------------------------------------
    # Quest assignment
    # ------------------------------------------------------------------

    def assign_portal_quest(self, map_key: str | tuple) -> dict:
        """Deterministically assign a portal quest for *map_key*."""
        game = self.game
        seed = hash((game.sectors.world_seed, str(map_key))) & 0xFFFF_FFFF
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
            if (
                isinstance(map_key, tuple)
                and len(map_key) == 3
                and map_key[0] == MapType.SECTOR
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
        else:
            quest = {
                "type": PortalQuestType.COMBAT,
                "restored": False,
                "guardian_defeated": False,
                "guardian_spawned": False,
            }

        self.portal_quests[map_key] = quest
        return quest

    # ------------------------------------------------------------------
    # Map placement
    # ------------------------------------------------------------------

    def place_portal_on_map(self, game_map: GameMap, map_key: str | tuple) -> None:
        """Place portal tiles on a newly generated island map."""
        game = self.game
        quest = self.portal_quests.get(map_key)
        if quest is None:
            return

        seed = hash((game.sectors.world_seed, str(map_key), "place")) & 0xFFFF_FFFF
        rng = random.Random(seed)

        rows, cols = game_map.rows, game_map.cols
        cx, cy = cols // 2, rows // 2
        min_dist = 12

        candidates = [
            (c, r)
            for r in range(rows)
            for c in range(cols)
            if game_map.get_tile(r, c) == GRASS
            and abs(c - cx) + abs(r - cy) >= min_dist
        ]
        if not candidates:
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
                if all(abs(sc - ec) + abs(sr - er) >= 8 for ec, er in positions):
                    game_map.set_tile(sr, sc, ANCIENT_STONE)
                    positions.append((sc, sr))
                    if len(positions) >= quest["stones_total"]:
                        break
            game_map.ritual_stone_positions = positions

        if quest["type"] == PortalQuestType.COMBAT:
            game_map.portal_guardian_spawned = quest.get("guardian_spawned", False)

    def place_sky_ladder_quest(self, game_map: MapScene) -> None:
        """Place the broken ladder and sign on the overland map."""
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
    # Quest checking / restoration
    # ------------------------------------------------------------------

    def check_portal_restored(self, map_key: str | tuple) -> bool:
        """Return True if the portal quest for *map_key* is (now) restored."""
        game = self.game
        quest = self.portal_quests.get(map_key)
        if quest is None:
            return False
        if quest["restored"]:
            return True

        complete = False
        if quest["type"] == PortalQuestType.RITUAL:
            complete = quest["stones_activated"] >= quest["stones_total"]
        elif quest["type"] == PortalQuestType.GATHER:
            complete = True
        elif quest["type"] == PortalQuestType.COMBAT:
            complete = quest.get("guardian_defeated", False)

        if complete:
            quest["restored"] = True
            game_map = game.maps.get(map_key)
            if game_map is not None and hasattr(game_map, "portal_col"):
                game_map.set_tile(
                    game_map.portal_row, game_map.portal_col, PORTAL_ACTIVE
                )
            return True
        return False

    def on_sentinel_defeated(self, map_key: str | tuple) -> None:
        """Handle a portal guardian being defeated."""
        game = self.game
        quest = self.portal_quests.get(map_key)
        if quest is None or quest["type"] != PortalQuestType.COMBAT:
            return
        quest["guardian_defeated"] = True
        if self.check_portal_restored(map_key):
            for player in (game.player1, game.player2):
                if player.current_map == map_key:
                    self.announce_portal_restored(player)
                    break

    # ------------------------------------------------------------------
    # Interaction handlers
    # ------------------------------------------------------------------

    def try_activate_ritual_stone(
        self,
        player: "Player",
        game_map: GameMap,
        stone_col: int,
        stone_row: int,
    ) -> None:
        """Handle a player interacting with an ANCIENT_STONE tile."""
        game = self.game
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
            game.floats.append(
                FloatingText(
                    tx, ty - 30, "Stone awakened!", (200, 180, 50), player.current_map
                )
            )
            for _ in range(10):
                game.particles.append(
                    Particle(tx, ty, (200, 180, 50), player.current_map)
                )
            if remaining == 0:
                if self.check_portal_restored(map_key):
                    self.announce_portal_restored(player)
        else:
            game.floats.append(
                FloatingText(
                    tx,
                    ty - 30,
                    "Not the next stone!",
                    (255, 100, 100),
                    player.current_map,
                )
            )

    def try_interact_portal_ruins(self, player: "Player", map_key: str | tuple) -> None:
        """Handle a player interacting with a PORTAL_RUINS tile."""
        game = self.game
        quest = self.portal_quests.get(map_key)
        tx = int(player.x)
        ty = int(player.y) - 36

        if quest is None:
            game.floats.append(
                FloatingText(
                    tx, ty, "Ancient portal...", (180, 160, 200), player.current_map
                )
            )
            return

        if quest["restored"]:
            game.floats.append(
                FloatingText(
                    tx, ty, "Portal is active!", (160, 60, 220), player.current_map
                )
            )
            return

        if quest["type"] == PortalQuestType.RITUAL:
            done = quest["stones_activated"]
            total = quest["stones_total"]
            game.floats.append(
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
            can_afford = all(
                player.inventory.get(k, 0) >= v for k, v in required.items()
            )
            if can_afford:
                from src.world import try_spend as _try_spend

                if _try_spend(player.inventory, required):
                    if self.check_portal_restored(map_key):
                        self.announce_portal_restored(player)
            else:
                parts = ", ".join(f"{v} {k}" for k, v in required.items())
                game.floats.append(
                    FloatingText(
                        tx, ty, f"Need: {parts}", (255, 160, 80), player.current_map
                    )
                )

        elif quest["type"] == PortalQuestType.COMBAT:
            if quest.get("guardian_defeated"):
                if self.check_portal_restored(map_key):
                    self.announce_portal_restored(player)
            else:
                game.floats.append(
                    FloatingText(
                        tx,
                        ty,
                        "A guardian blocks the portal!",
                        (200, 80, 80),
                        player.current_map,
                    )
                )

    def announce_portal_restored(self, player: "Player") -> None:
        """Show floating text + particles for portal restoration."""
        game = self.game
        game.floats.append(
            FloatingText(
                int(player.x),
                int(player.y) - 50,
                "Portal restored!",
                (160, 60, 220),
                player.current_map,
            )
        )
        for _ in range(20):
            game.particles.append(
                Particle(
                    int(player.x), int(player.y), (160, 60, 220), player.current_map
                )
            )
        self.add_realm_portal(player.current_map)

    # ------------------------------------------------------------------
    # Realm management
    # ------------------------------------------------------------------

    def _expand_realm(
        self,
        realm_map: GameMap,
        left: int,
        right: int,
        top: int,
        bottom: int,
    ) -> None:
        """Grow the realm's world array by the given number of slots."""
        slot_size = realm_map.slot_size
        add_left = left * slot_size
        add_top = top * slot_size
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
        if hasattr(realm_map, "slot_cols"):
            realm_map.slot_cols += left + right
        if hasattr(realm_map, "slot_rows"):
            realm_map.slot_rows += top + bottom
        new_exits: dict = {}
        for (col, row), mk in realm_map.portal_exits.items():
            new_exits[(col + add_left, row + add_top)] = mk
        realm_map.portal_exits = new_exits

    def _ensure_realm_slot(self, sx: int, sy: int) -> tuple[int, int]:
        """Ensure the realm has a carved chamber for sector (sx, sy)."""
        from src.world.environments.portal_realm import carve_chamber
        from src.world.environments.utils import connect_regions
        from src.config import PORTAL_FLOOR, TREASURE_CHEST, PORTAL_ACTIVE as _PA

        game = self.game
        realm_map = game.maps["portal_realm"]
        slot_size = realm_map.slot_size
        slot_pad = getattr(realm_map, "slot_padding", 0)
        origin_sx = realm_map.origin_sx
        origin_sy = realm_map.origin_sy
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

        carve_chamber(realm_map, slot_col, slot_row)
        connect_regions(
            realm_map.world,
            realm_map.rows,
            realm_map.cols,
            realm_map.spawn_col,
            realm_map.spawn_row,
            {PORTAL_FLOOR, TREASURE_CHEST, _PA},
            PORTAL_FLOOR,
            getattr(realm_map, "slot_padding", 2),
        )

        portal_col = slot_col + slot_size // 2
        portal_row = slot_row + slot_size // 2
        return portal_col, portal_row

    def _add_realm_chest_near(
        self, realm_map: GameMap, portal_col: int, portal_row: int
    ) -> None:
        """Place a TREASURE_CHEST near the portal in the realm."""
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

    def add_realm_portal(self, dest_map_key: str | tuple) -> None:
        """Place a PORTAL_ACTIVE tile in the portal realm linking to *dest_map_key*."""
        game = self.game
        if "portal_realm" not in game.maps:
            return
        coords = game.sectors.get_sector_coords(dest_map_key)
        if coords is None:
            return

        realm_map = game.maps["portal_realm"]
        if not hasattr(realm_map, "portal_exits"):
            realm_map.portal_exits = {}
        if not hasattr(realm_map, "slot_size"):
            return
        if dest_map_key in realm_map.portal_exits.values():
            return

        sx, sy = coords
        portal_col, portal_row = self._ensure_realm_slot(sx, sy)
        realm_map.world[portal_row][portal_col] = PORTAL_ACTIVE
        realm_map.portal_exits[(portal_col, portal_row)] = dest_map_key

        self._add_realm_chest_near(realm_map, portal_col, portal_row)

    # ------------------------------------------------------------------
    # Enter / exit portal realm
    # ------------------------------------------------------------------

    def enter_portal_realm(self, player: "Player") -> None:
        """Teleport the player into the portal realm."""
        from src.world.environments import PortalRealmEnvironment

        game = self.game
        origin_key = player.current_map

        if "portal_realm" in game.maps:
            rm = game.maps["portal_realm"]
            if not hasattr(rm, "slot_size") or not hasattr(rm, "origin_sx"):
                del game.maps["portal_realm"]

        if "portal_realm" not in game.maps:
            env = PortalRealmEnvironment()
            _realm_scene = MapScene(env.generate())
            finalize_scene(_realm_scene, PORTAL_FLOOR)
            game.maps["portal_realm"] = _realm_scene
            for mk, quest in self.portal_quests.items():
                if quest.get("restored"):
                    self.add_realm_portal(mk)

        self.add_realm_portal(origin_key)

        realm_map = game.maps["portal_realm"]

        origin_portal = next(
            (
                (c, r)
                for (c, r), mk in realm_map.portal_exits.items()
                if mk == origin_key
            ),
            None,
        )
        if origin_portal is not None:
            dest_x = origin_portal[0] * TILE + TILE // 2
            dest_y = origin_portal[1] * TILE + TILE // 2
        else:
            dest_x = realm_map.spawn_col * TILE + TILE // 2
            dest_y = realm_map.spawn_row * TILE + TILE // 2

        # Start the vortex over the OLD scene; defer move to midpoint
        self.portal_warp[player.player_id] = {
            "progress": 0.0,
            "switched": False,
            "pending": {
                "pid": player.player_id,
                "current_map": "portal_realm",
                "x": dest_x,
                "y": dest_y,
                "portal_origin_map": origin_key,
                "clear_portal_origin": False,
                "float_text": "Entered portal realm!",
                "float_color": (160, 60, 220),
            },
        }

    def exit_portal_realm(
        self,
        player: "Player",
        portal_col: int | None = None,
        portal_row: int | None = None,
    ) -> None:
        """Return the player from the portal realm."""
        game = self.game
        realm_map = game.maps.get("portal_realm")
        dest_key: str | tuple | None = None
        if (
            realm_map is not None
            and portal_col is not None
            and hasattr(realm_map, "portal_exits")
        ):
            dest_key = realm_map.portal_exits.get((portal_col, portal_row))

        if dest_key is None:
            dest_key = player.portal_origin_map or "overland"

        dest_map = game.maps.get(dest_key)
        if dest_map is None:
            dest_key = "overland"
            dest_map = game.maps["overland"]

        p_col = getattr(dest_map, "portal_col", dest_map.cols // 2)
        p_row = getattr(dest_map, "portal_row", dest_map.rows // 2)
        dest_x: float | None = None
        dest_y: float | None = None
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
                    dest_x = adj_c * TILE + TILE // 2
                    dest_y = adj_r * TILE + TILE // 2
                    break
        if dest_x is None:
            dest_x = p_col * TILE + TILE // 2
            dest_y = p_row * TILE + TILE // 2

        # Start the vortex over the OLD scene; defer move to midpoint
        self.portal_warp[player.player_id] = {
            "progress": 0.0,
            "switched": False,
            "pending": {
                "pid": player.player_id,
                "current_map": dest_key,
                "x": dest_x,
                "y": dest_y,
                "portal_origin_map": None,
                "clear_portal_origin": True,
                "last_portal_exit_map": dest_key,
                "last_portal_exit_x": dest_x,
                "last_portal_exit_y": dest_y,
                "float_text": "Left portal realm!",
                "float_color": (180, 160, 220),
            },
        }

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------

    def debug_force_portal_on_map(
        self, map_key: str | tuple, game_map: GameMap
    ) -> None:
        """Force-complete the portal quest for *map_key*."""
        if map_key not in self.portal_quests:
            self.assign_portal_quest(map_key)
            self.place_portal_on_map(game_map, map_key)

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
            self.check_portal_restored(map_key)

    def debug_ensure_nearby_island(self, origin_sx: int, origin_sy: int) -> None:
        """Expand outward from origin until two sectors with islands are found,
        generating them if needed, and force-restoring their portals."""
        game = self.game
        found = 0
        for dist in range(1, 16):
            for dx in range(-dist, dist + 1):
                for dy in range(-dist, dist + 1):
                    if abs(dx) != dist and abs(dy) != dist:
                        continue
                    sx, sy = origin_sx + dx, origin_sy + dy
                    sector_map = game.sectors.get_or_generate_sector(sx, sy)
                    game.sectors.visited_sectors.add((sx, sy))
                    if (sx, sy) not in game.sectors.land_sectors:
                        continue
                    sector_key = (
                        ("sector", sx, sy) if (sx, sy) != (0, 0) else "overland"
                    )
                    self.debug_force_portal_on_map(sector_key, sector_map)
                    self.add_realm_portal(sector_key)
                    found += 1
                    if found >= 2:
                        return

    # ------------------------------------------------------------------
    # Frame tick
    # ------------------------------------------------------------------

    def tick_warp(self, dt: float) -> None:
        """Advance portal-warp animation timers."""
        for pid in list(self.portal_warp.keys()):
            state = self.portal_warp[pid]
            state["progress"] += dt / PORTAL_WARP_DURATION
            # At the midpoint flash, execute the deferred scene switch
            if not state.get("switched", True) and state["progress"] >= 0.5:
                self._execute_warp_switch(state["pending"])
                state["switched"] = True
            if state["progress"] >= 1.0:
                del self.portal_warp[pid]

    def _execute_warp_switch(self, pending: dict) -> None:
        """Apply the deferred player teleport at the warp midpoint."""
        game = self.game
        pid: int = pending["pid"]
        player = game.player1 if pid == 1 else game.player2

        if pending.get("clear_portal_origin"):
            player.portal_origin_map = None
        elif "portal_origin_map" in pending:
            player.portal_origin_map = pending["portal_origin_map"]

        player.current_map = pending["current_map"]
        player.x = pending["x"]
        player.y = pending["y"]

        for attr in (
            "last_portal_exit_map",
            "last_portal_exit_x",
            "last_portal_exit_y",
        ):
            if attr in pending:
                setattr(player, attr, pending[attr])

        game._snap_camera_to_player(player)

        game.floats.append(
            FloatingText(
                int(player.x),
                int(player.y) - 30,
                pending["float_text"],
                pending["float_color"],
                player.current_map,
            )
        )
