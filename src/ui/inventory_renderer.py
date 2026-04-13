"""Inventory overlay rendering and input handling.

Extracted from game.py — owns all inventory UI state and rendering logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.config import TILE
from src.data import PICKAXES, ARMOR_PIECES, ACCESSORY_PIECES
from src.data.attack_patterns import WEAPON_REGISTRY
from src.effects import Particle, FloatingText
from src.ui.inventory import (
    InventoryState,
    InventoryTab,
    NUM_TABS,
    DOLL_SLOTS,
    DOLL_SLOT_POSITIONS,
    DOLL_VIRTUAL_SLOTS,
    DOLL_VIRTUAL_SLOT_TABS,
    TAB_LABELS,
    TAB_SPRITE_IDS,
    item_sprite_id,
    get_tab_items,
    auto_equip_slot,
)
from src.world import try_spend

if TYPE_CHECKING:
    from src.entities.player import Player


class InventoryRenderer:
    """Full inventory overlay — input handling, rendering, and icon caching.

    Owns ``_inventory_open``, ``_inventory_ui``, and ``_inv_icon_cache``.
    Receives a *game* reference for access to fonts, screen, maps, and helpers.
    """

    # Layout constants (relative to each player's viewport)
    DOLL_W: int = 280
    CELL: int = 72
    GAP: int = 5
    COLS: int = 8
    TAB_H: int = 68
    TOOLTIP_H: int = 165
    SLOT_SZ: int = 40

    def __init__(self, game: object) -> None:
        self.game = game
        self._open: dict[int, bool] = {1: False, 2: False}
        self._ui: dict[int, InventoryState] = {1: InventoryState(), 2: InventoryState()}
        self._icon_cache: dict[tuple[str, int], pygame.Surface] = {}

    # ------------------------------------------------------------------
    # Public API used by Game
    # ------------------------------------------------------------------

    def is_open(self, player_id: int) -> bool:
        return self._open.get(player_id, False)

    def toggle(self, player_id: int) -> None:
        self._open[player_id] = not self._open[player_id]
        if self._open[player_id]:
            self._ui[player_id] = InventoryState()

    def open_to_tab(self, player_id: int, tab: InventoryTab) -> None:
        """Open the inventory directly to a specific tab."""
        self._open[player_id] = True
        self._ui[player_id] = InventoryState()
        self._ui[player_id].tab = tab

    def close(self, player_id: int) -> None:
        self._open[player_id] = False

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_input(self, key: int, player: "Player") -> None:
        """Process one KEYDOWN event while the inventory is open for *player*."""
        pid = player.player_id
        state = self._ui[pid]
        up_k = player.controls.move_keys["up"]
        down_k = player.controls.move_keys["down"]
        left_k = player.controls.move_keys["left"]
        right_k = player.controls.move_keys["right"]
        if pid == 1:
            prev_tab_key, next_tab_key = pygame.K_z, pygame.K_x
        else:
            prev_tab_key, next_tab_key = pygame.K_COMMA, pygame.K_PERIOD

        # Close inventory
        if key in (pygame.K_ESCAPE, player.controls.equip_key):
            self._open[pid] = False
            return

        # --- Ring-disambiguation sub-state ---
        if state.ring_pick_item is not None:
            if key in (up_k, down_k):
                state.ring_pick_choice ^= 1
            elif key == player.controls.interact_key:
                slot_key = "ring1" if state.ring_pick_choice == 0 else "ring2"
                item_name = state.ring_pick_item
                if player.equip_item(slot_key, item_name):
                    self._float(player, f"Equipped {item_name}!")
                state.ring_pick_item = None
            elif key == pygame.K_ESCAPE:
                state.ring_pick_item = None
            return

        # --- Tab switch ---
        if key == prev_tab_key:
            state.tab = InventoryTab((state.tab - 1) % NUM_TABS)
            state.grid_idx = 0
            state.scroll_offset = 0
            state.doll_focus = False
            return
        if key == next_tab_key:
            state.tab = InventoryTab((state.tab + 1) % NUM_TABS)
            state.grid_idx = 0
            state.scroll_offset = 0
            state.doll_focus = False
            return

        # --- Doll navigation ---
        if state.doll_focus:
            num_slots = len(DOLL_SLOTS)
            if key == up_k:
                state.doll_slot_idx = (state.doll_slot_idx - 1) % num_slots
            elif key == down_k:
                state.doll_slot_idx = (state.doll_slot_idx + 1) % num_slots
            elif key == right_k:
                state.doll_focus = False
            elif key == player.controls.interact_key:
                slot_key = DOLL_SLOTS[state.doll_slot_idx]
                self._doll_confirm(player, state, slot_key)
            return

        # --- Grid navigation ---
        items = get_tab_items(player, state.tab)
        num_items = len(items)
        cols = self.COLS

        if key == left_k:
            col = state.grid_idx % cols
            if col == 0:
                state.doll_focus = True
            else:
                state.grid_idx -= 1
        elif key == right_k:
            col = state.grid_idx % cols
            if col < cols - 1 and state.grid_idx < num_items - 1:
                state.grid_idx += 1
        elif key == up_k:
            new_idx = state.grid_idx - cols
            if new_idx >= 0:
                state.grid_idx = new_idx
        elif key == down_k:
            new_idx = state.grid_idx + cols
            if new_idx < num_items:
                state.grid_idx = new_idx
        elif key == player.controls.interact_key and num_items > 0:
            item = items[state.grid_idx]
            self._grid_confirm(player, state, item)
            return

        if num_items > 0:
            state.grid_idx = max(0, min(state.grid_idx, num_items - 1))
        self._update_scroll(state, num_items)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_scroll(self, state: InventoryState, num_items: int) -> None:
        visible_rows = self._visible_rows()
        row = state.grid_idx // self.COLS
        if row < state.scroll_offset:
            state.scroll_offset = row
        elif row >= state.scroll_offset + visible_rows:
            state.scroll_offset = row - visible_rows + 1

    def _visible_rows(self) -> int:
        grid_h = self.game.viewport_h - self.TAB_H - self.TOOLTIP_H - 8
        return max(1, grid_h // (self.CELL + self.GAP))

    def _float(
        self, player: "Player", text: str, color: tuple[int, int, int] = (100, 220, 100)
    ) -> None:
        self.game.floats.append(
            FloatingText(
                int(player.x), int(player.y) - 20, text, color, player.current_map
            )
        )

    def _doll_confirm(
        self, player: "Player", state: InventoryState, slot_key: str
    ) -> None:
        if slot_key in DOLL_VIRTUAL_SLOTS:
            state.doll_focus = False
            state.tab = DOLL_VIRTUAL_SLOT_TABS[slot_key]
            state.grid_idx = 0
            state.scroll_offset = 0
            return
        if player.equipment.get(slot_key) is not None:
            player.unequip_item(slot_key)
            self._float(player, "Unequipped", (200, 200, 100))
        else:
            if slot_key in ("ring1", "ring2", "amulet"):
                state.tab = InventoryTab.ACCESSORIES
            else:
                state.tab = InventoryTab.ARMOR
            state.doll_focus = False
            state.grid_idx = 0
            state.scroll_offset = 0

    def _grid_confirm(
        self, player: "Player", state: InventoryState, item: dict
    ) -> None:
        itype = item["type"]

        if itype in ("armor", "accessory"):
            slot_key = auto_equip_slot(item, player)
            if slot_key is None:
                state.ring_pick_item = item["name"]
                state.ring_pick_choice = 0
            else:
                if player.equip_item(slot_key, item["name"]):
                    self._float(player, f"Equipped {item['name']}!")

        elif itype == "weapon":
            if item["can_upgrade"]:
                player.try_upgrade_weapon()
                self._float(player, f"Upgraded to {item['name']}!", (255, 200, 50))
                state.grid_idx = player.weapon_level
            else:
                state.message = "Cannot upgrade yet"
                state.message_timer = 2.0

        elif itype == "pickaxe":
            if item["can_upgrade"]:
                player.try_upgrade_pick()
                self._float(player, f"Upgraded to {item['name']}!", (255, 200, 50))
                state.grid_idx = player.pick_level
            else:
                state.message = "Cannot upgrade yet"
                state.message_timer = 2.0

        elif itype == "recipe":
            self._craft(player, state, item)

    def _craft(self, player: "Player", state: InventoryState, item: dict) -> None:
        min_tier: int = item["min_tier"]
        is_in_housing = self.game._is_in_housing_env(player)
        housing_tier = getattr(
            self.game.get_player_current_map(player), "housing_tier", 0
        )

        if min_tier > 0 and not is_in_housing:
            state.message = "Visit a settlement to craft this"
            state.message_timer = 2.5
            return
        if min_tier > 0 and housing_tier < min_tier:
            state.message = f"Requires settlement tier {min_tier}"
            state.message_timer = 2.5
            return

        if try_spend(player.inventory, item["cost"]):
            result = item["result"]
            player.inventory[result["item"]] = (
                player.inventory.get(result["item"], 0) + result["qty"]
            )
            self._float(
                player,
                f"Crafted {result['qty']}×{result['item']}!",
                (60, 200, 255),
            )
            for _ in range(8):
                self.game.particles.append(
                    Particle(
                        int(player.x),
                        int(player.y) - 20,
                        (40, 160, 220),
                        player.current_map,
                    )
                )
        else:
            cost_str = ", ".join(f"{v}×{k}" for k, v in item["cost"].items())
            state.message = f"Need {cost_str}"
            state.message_timer = 2.0

    # ------------------------------------------------------------------
    # Icon caching
    # ------------------------------------------------------------------

    def get_icon(self, sprite_id: str, size: int) -> pygame.Surface | None:
        cache_key = (sprite_id, size)
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        from src.rendering.registry import SpriteRegistry

        reg = SpriteRegistry.get_instance()
        result = reg.get(sprite_id)
        if result is None:
            return None
        sheet, manifest = result
        fw = manifest["frame_size"][0]
        fh = manifest["frame_size"][1]
        frame = sheet.subsurface((0, 0, fw, fh))
        icon = pygame.transform.smoothscale(frame, (size, size))
        self._icon_cache[cache_key] = icon
        return icon

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(
        self,
        player: "Player",
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        """Draw the full inventory overlay for *player*'s viewport."""
        state = self._ui[player.player_id]
        screen = self.game.screen

        # Tick transient message timer
        state.message_timer = max(0.0, state.message_timer - 1.0 / 60.0)
        if state.message_timer <= 0.0:
            state.message = ""

        doll_w = self.DOLL_W
        grid_x = screen_x + doll_w
        grid_w = view_w - doll_w

        overlay = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (screen_x, screen_y))

        self._draw_doll(player, state, screen_x, screen_y, doll_w, view_h)
        self._draw_grid(player, state, grid_x, screen_y, grid_w, view_h)

        pygame.draw.line(
            screen,
            (80, 70, 120),
            (screen_x + doll_w, screen_y + 4),
            (screen_x + doll_w, screen_y + view_h - 4),
            1,
        )

    def _draw_doll(
        self,
        player: "Player",
        state: InventoryState,
        bx: int,
        by: int,
        w: int,
        h: int,
    ) -> None:
        """Draw the character-doll panel."""
        screen = self.game.screen
        font_xs = self.game.font_ui_xs
        font_sm = self.game.font_ui_sm

        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((18, 14, 30, 230))
        screen.blit(panel, (bx, by))

        title = font_sm.render("Character", True, (200, 180, 255))
        screen.blit(title, (bx + (w - title.get_width()) // 2, by + 12))

        fig_col = (70, 62, 100)
        cx = bx + w // 2
        fy = by + 50
        pygame.draw.circle(screen, fig_col, (cx, fy + 38), 24, 2)
        pygame.draw.line(screen, fig_col, (cx, fy + 62), (cx, fy + 78), 3)
        pygame.draw.rect(
            screen, fig_col, (cx - 30, fy + 78, 60, 62), 2, border_radius=3
        )
        pygame.draw.line(screen, fig_col, (cx - 30, fy + 90), (cx - 78, fy + 120), 3)
        pygame.draw.line(screen, fig_col, (cx + 30, fy + 90), (cx + 78, fy + 120), 3)
        pygame.draw.line(screen, fig_col, (cx - 15, fy + 140), (cx - 20, fy + 212), 3)
        pygame.draw.line(screen, fig_col, (cx + 15, fy + 140), (cx + 20, fy + 212), 3)

        slot_sz = self.SLOT_SZ
        for si, slot_key in enumerate(DOLL_SLOTS):
            rx, ry = DOLL_SLOT_POSITIONS[slot_key]
            ax, ay = bx + rx, by + ry

            is_selected = state.doll_focus and si == state.doll_slot_idx
            is_virtual = slot_key in DOLL_VIRTUAL_SLOTS

            bg_col = (40, 35, 65) if not is_virtual else (35, 50, 40)
            pygame.draw.rect(screen, bg_col, (ax, ay, slot_sz, slot_sz), border_radius=3)

            if slot_key == "weapon":
                wpn_def = WEAPON_REGISTRY.get(player.weapon_id)
                if wpn_def is not None:
                    icon = self.get_icon(item_sprite_id(wpn_def.name), slot_sz)
                    if icon:
                        screen.blit(icon, (ax, ay))
                    else:
                        pygame.draw.rect(
                            screen,
                            wpn_def.color,
                            (ax + 4, ay + 4, slot_sz - 8, slot_sz - 8),
                            border_radius=2,
                        )
            elif slot_key == "pickaxe":
                pick = PICKAXES[player.pick_level]
                icon = self.get_icon(item_sprite_id(pick["name"]), slot_sz)
                if icon:
                    screen.blit(icon, (ax, ay))
                else:
                    pygame.draw.rect(
                        screen,
                        pick["color"],
                        (ax + 4, ay + 4, slot_sz - 8, slot_sz - 8),
                        border_radius=2,
                    )
            else:
                equipped = player.equipment.get(slot_key)
                if equipped:
                    icon = self.get_icon(item_sprite_id(equipped), slot_sz)
                    if icon:
                        screen.blit(icon, (ax, ay))
                    else:
                        if equipped in ARMOR_PIECES:
                            ec = ARMOR_PIECES[equipped]["color"]
                        elif equipped in ACCESSORY_PIECES:
                            ec = ACCESSORY_PIECES[equipped]["color"]
                        else:
                            ec = (120, 120, 120)
                        pygame.draw.rect(
                            screen,
                            ec,
                            (ax + 4, ay + 4, slot_sz - 8, slot_sz - 8),
                            border_radius=2,
                        )

            border_col = (
                (255, 220, 60)
                if is_selected
                else (100, 90, 140) if not is_virtual else (70, 110, 70)
            )
            pygame.draw.rect(
                screen, border_col, (ax, ay, slot_sz, slot_sz), 2, border_radius=3
            )

        stat_y = by + 318
        def_pct = int(player.defense_pct * 100)
        def_surf = font_xs.render(f"Defense: {def_pct}%", True, (160, 220, 160))
        screen.blit(def_surf, (bx + (w - def_surf.get_width()) // 2, stat_y))

        hint_y = stat_y + 72
        close_key_name = pygame.key.name(player.controls.equip_key).upper()
        tab_key = "Z/X" if player.player_id == 1 else ",/."
        for txt, col in [
            (f"{close_key_name}: Close", (140, 130, 160)),
            (f"{tab_key}: Switch Tab", (120, 110, 140)),
            ("← Enter doll", (120, 110, 140)),
        ]:
            surf = font_xs.render(txt, True, col)
            screen.blit(surf, (bx + 8, hint_y))
            hint_y += 16

    def _draw_grid(
        self,
        player: "Player",
        state: InventoryState,
        bx: int,
        by: int,
        w: int,
        h: int,
    ) -> None:
        """Draw the tab strip + item grid + tooltip."""
        screen = self.game.screen
        font_xs = self.game.font_ui_xs
        font_sm = self.game.font_ui_sm

        tab_h = self.TAB_H
        tooltip_h = self.TOOLTIP_H
        cell = self.CELL
        gap = self.GAP
        cols = self.COLS

        tab_w = w // NUM_TABS
        for ti in range(NUM_TABS):
            tx = bx + ti * tab_w
            ty = by
            is_active = ti == state.tab

            tab_bg = (40, 36, 68) if is_active else (22, 20, 36)
            pygame.draw.rect(screen, tab_bg, (tx, ty, tab_w, tab_h))
            border_col = (200, 160, 255) if is_active else (55, 50, 80)
            pygame.draw.rect(screen, border_col, (tx, ty, tab_w, tab_h), 1)

            icon = self.get_icon(TAB_SPRITE_IDS[ti], 36)
            icon_x = tx + (tab_w - 36) // 2
            icon_y = ty + 4
            if icon:
                if not is_active:
                    dimmed = icon.copy()
                    dimmed.set_alpha(130)
                    screen.blit(dimmed, (icon_x, icon_y))
                else:
                    screen.blit(icon, (icon_x, icon_y))
            label_col = (220, 200, 255) if is_active else (120, 110, 150)
            lbl = font_xs.render(TAB_LABELS[ti], True, label_col)
            screen.blit(lbl, (tx + (tab_w - lbl.get_width()) // 2, ty + 44))

        grid_top = by + tab_h + 4
        grid_h = h - tab_h - tooltip_h - 8
        total_grid_w = cols * (cell + gap) - gap
        grid_left = bx + (w - total_grid_w) // 2

        screen.set_clip((bx, grid_top, w, grid_h))

        items = get_tab_items(player, state.tab)
        visible_rows = self._visible_rows()

        for idx, item in enumerate(items):
            row = idx // cols
            col_i = idx % cols
            if row < state.scroll_offset or row >= state.scroll_offset + visible_rows:
                continue
            sx = grid_left + col_i * (cell + gap)
            sy = grid_top + (row - state.scroll_offset) * (cell + gap)

            is_selected = (not state.doll_focus) and idx == state.grid_idx
            self._draw_cell(item, player, sx, sy, cell, is_selected, state)

        screen.set_clip(None)

        total_rows = (len(items) + cols - 1) // cols if items else 0
        if total_rows > visible_rows:
            sb_x = bx + w - 8
            sb_h = grid_h
            thumb_h = max(20, int(sb_h * visible_rows / total_rows))
            thumb_y = grid_top + int(
                (sb_h - thumb_h)
                * state.scroll_offset
                / max(1, total_rows - visible_rows)
            )
            pygame.draw.rect(
                screen, (40, 35, 65), (sb_x, grid_top, 6, sb_h), border_radius=3
            )
            pygame.draw.rect(
                screen,
                (130, 110, 180),
                (sb_x, thumb_y, 6, thumb_h),
                border_radius=3,
            )

        if state.ring_pick_item is not None:
            self._draw_ring_pick(state, bx, by, w, h)
            return

        tooltip_top = by + h - tooltip_h
        pygame.draw.line(
            screen, (60, 55, 90), (bx, tooltip_top), (bx + w, tooltip_top), 1
        )
        focused_item = (
            items[state.grid_idx] if (not state.doll_focus and items) else None
        )
        self._draw_tooltip(player, state, focused_item, bx, tooltip_top, w, tooltip_h)

    def _draw_cell(
        self,
        item: dict,
        player: "Player",
        sx: int,
        sy: int,
        cell: int,
        is_selected: bool,
        state: InventoryState,
    ) -> None:
        """Draw one grid cell."""
        screen = self.game.screen
        font_xs = self.game.font_ui_xs
        itype = item["type"]

        if itype in ("weapon", "pickaxe"):
            if item["is_current"]:
                bg = (30, 55, 30)
            elif item["is_past"]:
                bg = (22, 40, 22)
            elif item["can_upgrade"]:
                bg = (50, 50, 20)
            else:
                bg = (22, 20, 36)
        elif itype == "recipe":
            is_in_housing = self.game._is_in_housing_env(player)
            housing_tier = getattr(
                self.game.get_player_current_map(player), "housing_tier", 0
            )
            craftable = item["min_tier"] == 0 or (
                is_in_housing and housing_tier >= item["min_tier"]
            )
            if craftable and item["can_afford"]:
                bg = (20, 45, 20)
            elif craftable:
                bg = (45, 35, 10)
            else:
                bg = (22, 20, 36)
        else:
            bg = (28, 24, 44)

        pygame.draw.rect(screen, bg, (sx, sy, cell, cell), border_radius=4)

        sprite_id = item_sprite_id(item["name"])
        icon = self.get_icon(sprite_id, cell - 4)
        if icon:
            if itype in ("weapon", "pickaxe") and item.get("is_locked"):
                dimmed = icon.copy()
                dimmed.set_alpha(80)
                screen.blit(dimmed, (sx + 2, sy + 2))
            else:
                screen.blit(icon, (sx + 2, sy + 2))
        else:
            fb_col = item.get("color", (120, 120, 140))
            pygame.draw.rect(
                screen,
                fb_col,
                (sx + 8, sy + 8, cell - 16, cell - 16),
                border_radius=3,
            )

        if item["count"] > 1:
            ct = font_xs.render(str(item["count"]), True, (240, 240, 240))
            screen.blit(ct, (sx + cell - ct.get_width() - 3, sy + cell - 14))

        if itype in ("weapon", "pickaxe") and item["is_current"]:
            pygame.draw.circle(screen, (100, 230, 100), (sx + cell - 6, sy + 6), 4)

        if is_selected:
            pygame.draw.rect(
                screen, (255, 220, 60), (sx, sy, cell, cell), 2, border_radius=4
            )
        elif itype in ("weapon", "pickaxe") and item["is_current"]:
            pygame.draw.rect(
                screen, (80, 200, 80), (sx, sy, cell, cell), 1, border_radius=4
            )
        else:
            pygame.draw.rect(
                screen, (55, 50, 82), (sx, sy, cell, cell), 1, border_radius=4
            )

    def _draw_tooltip(
        self,
        player: "Player",
        state: InventoryState,
        item: dict | None,
        bx: int,
        by: int,
        w: int,
        h: int,
    ) -> None:
        """Draw the tooltip strip at the bottom of the grid panel."""
        screen = self.game.screen
        font_sm = self.game.font_ui_sm
        font_xs = self.game.font_ui_xs
        PADX = 14

        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((14, 12, 24, 210))
        screen.blit(bg, (bx, by))

        if state.message:
            msg = font_sm.render(state.message, True, (255, 180, 80))
            screen.blit(msg, (bx + PADX, by + (h - msg.get_height()) // 2))
            return

        if item is None:
            return

        itype = item["type"]
        name_surf = font_sm.render(item["name"], True, (220, 210, 255))
        screen.blit(name_surf, (bx + PADX, by + 10))

        y = by + 36
        line_h = 18

        def _line(text: str, col: tuple[int, ...] = (180, 175, 210)) -> None:
            nonlocal y
            screen.blit(font_xs.render(text, True, col), (bx + PADX, y))
            y += line_h

        if itype == "armor":
            _line(
                f"Slot: {item['slot'].capitalize()}  |  Defense: {int(item['defense_pct'] * 100)}%  |  Durability: {item['durability']}"
            )
            equipped_in = [
                s
                for s in ("helmet", "chest", "legs", "boots")
                if player.equipment.get(s) == item["name"]
            ]
            if equipped_in:
                _line(f"Equipped in: {', '.join(equipped_in)}", (100, 220, 100))
            _line("E — Equip", (255, 220, 80))

        elif itype == "accessory":
            _line(f"Slot: {item['slot'].capitalize()}  |  {item['label']}")
            equipped_in = [
                s
                for s in ("ring1", "ring2", "amulet")
                if player.equipment.get(s) == item["name"]
            ]
            if equipped_in:
                _line(f"Equipped in: {', '.join(equipped_in)}", (100, 220, 100))
            _line("E — Equip", (255, 220, 80))

        elif itype == "weapon":
            wpn = item["weapon_data"]
            _line(
                f"DMG {wpn['damage']}  |  Range {wpn['distance'] // TILE}t  |  Cooldown {wpn['cooldown']}f  {'| Piercing' if wpn.get('pierce') else ''}"
            )
            if item["is_current"]:
                _line("Current weapon", (100, 220, 100))
            elif item["is_past"]:
                _line("Already surpassed", (120, 120, 120))
            elif item["can_upgrade"]:
                cost_str = "  ".join(
                    f"{v}×{k}" for k, v in item["upgrade_cost"].items()
                )
                _line(f"E — Upgrade  ({cost_str})", (255, 220, 80))
            else:
                cost_str = (
                    "  ".join(f"{v}×{k}" for k, v in item["upgrade_cost"].items())
                    if item["upgrade_cost"]
                    else "—"
                )
                _line(f"Unlock cost: {cost_str}", (180, 120, 80))

        elif itype == "pickaxe":
            _line(f"Power: {item['pick_data']['power']}")
            if item["is_current"]:
                _line("Current pickaxe", (100, 220, 100))
            elif item["is_past"]:
                _line("Already surpassed", (120, 120, 120))
            elif item["can_upgrade"]:
                cost_str = "  ".join(
                    f"{v}×{k}" for k, v in item["upgrade_cost"].items()
                )
                _line(f"E — Upgrade  ({cost_str})", (255, 220, 80))
            else:
                cost_str = (
                    "  ".join(f"{v}×{k}" for k, v in item["upgrade_cost"].items())
                    if item["upgrade_cost"]
                    else "—"
                )
                _line(f"Unlock cost: {cost_str}", (180, 120, 80))

        elif itype == "material":
            _line(f"Qty: {item['count']}")

        elif itype == "recipe":
            cost_str = "  ".join(f"{v}×{k}" for k, v in item["cost"].items())
            result = item["result"]
            _line(f"Cost: {cost_str}")
            _line(f"Result: {result['qty']}×{result['item']}")
            is_in_housing = self.game._is_in_housing_env(player)
            housing_tier = getattr(
                self.game.get_player_current_map(player), "housing_tier", 0
            )
            min_tier = item["min_tier"]
            if min_tier == 0:
                hint = "E — Craft (anywhere)"
            elif not is_in_housing:
                hint = "Visit a settlement to craft this"
            elif housing_tier < min_tier:
                hint = f"Requires settlement tier {min_tier}"
            else:
                hint = "E — Craft"
            hint_col = (
                (255, 220, 80)
                if (min_tier == 0 or (is_in_housing and housing_tier >= min_tier))
                else (180, 120, 80)
            )
            _line(hint, hint_col)
            if not item["can_afford"]:
                _line("(Missing materials)", (220, 100, 80))

    def _draw_ring_pick(
        self,
        state: InventoryState,
        bx: int,
        by: int,
        w: int,
        h: int,
    ) -> None:
        """Draw the ring-slot disambiguation overlay."""
        screen = self.game.screen
        font_sm = self.game.font_ui_sm
        font_xs = self.game.font_ui_xs

        ov_w, ov_h = 300, 90
        ox = bx + (w - ov_w) // 2
        oy = by + (h - ov_h) // 2

        bg = pygame.Surface((ov_w, ov_h), pygame.SRCALPHA)
        bg.fill((20, 15, 35, 240))
        screen.blit(bg, (ox, oy))
        pygame.draw.rect(
            screen, (200, 150, 255), (ox, oy, ov_w, ov_h), 2, border_radius=4
        )

        title = font_sm.render("Replace which ring?", True, (220, 200, 255))
        screen.blit(title, (ox + (ov_w - title.get_width()) // 2, oy + 8))

        for ci, label in enumerate(("Ring 1", "Ring 2")):
            ry = oy + 36 + ci * 22
            if ci == state.ring_pick_choice:
                pygame.draw.rect(
                    screen,
                    (70, 50, 130),
                    (ox + 6, ry, ov_w - 12, 20),
                    border_radius=2,
                )
            screen.blit(
                font_xs.render(label, True, (220, 220, 220)), (ox + 14, ry + 2)
            )
