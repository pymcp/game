"""Player viewport HUD — top stats panel, bottom controls, interaction hints, minimap.

Extracted from game.py ``_draw_player_ui`` and its helpers.
The class reads game state but does not own it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from src.config import (
    TILE,
    CAVE_MOUNTAIN,
    CAVE_HILL,
    CAVE_EXIT,
    HOUSE,
    SETTLEMENT_HOUSE,
    HOUSE_EXIT,
    WORKTABLE,
    SIGN,
    BROKEN_LADDER,
    SKY_LADDER,
    SETTLEMENT_TIER_SIZES,
    SETTLEMENT_TIER_NAMES,
    BiomeType,
)
from src.data import PICKAXES
from src.data.attack_patterns import WEAPON_REGISTRY
from src.world import get_sector_biome

if TYPE_CHECKING:
    from src.entities.player import Player


class PlayerHUD:
    """Draws the in-viewport HUD for a single player.

    This includes:
    * Top stats panel (HP, XP, gear, workers/pets)
    * Bottom controls panel
    * Context-sensitive interaction hints
    * Sector minimap
    * Sign text popup
    * Sky ascend/descend flash overlay
    """

    def __init__(self, game: object) -> None:
        self.game = game

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def draw(
        self,
        player: "Player",
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        """Draw all HUD elements for *player*'s viewport."""
        self._draw_top_panel(player, screen_x, screen_y)
        self._draw_bottom_panel(player, screen_x, screen_y, view_w, view_h)
        self._draw_interaction_hints(player, screen_x, screen_y, view_w, view_h)
        self._draw_sector_minimap(player, screen_x, screen_y, view_w, view_h)
        self._draw_sign_display(player, screen_x, screen_y, view_w, view_h)
        self._draw_sky_anim_overlay(player, screen_x, screen_y, view_w, view_h)

    # ------------------------------------------------------------------
    # Top stats panel
    # ------------------------------------------------------------------

    def _draw_top_panel(self, player: "Player", screen_x: int, screen_y: int) -> None:
        game = self.game
        screen = game.screen
        font_small = game.font_ui_sm
        font_tiny = game.font_ui_xs

        top_panel_w = 240
        top_panel_h = 148
        top_panel_surf = pygame.Surface((top_panel_w, top_panel_h), pygame.SRCALPHA)
        top_panel_surf.fill((20, 20, 30, 200))
        screen.blit(top_panel_surf, (screen_x + 8, screen_y + 8))
        pygame.draw.rect(
            screen,
            (150, 150, 150),
            (screen_x + 8, screen_y + 8, top_panel_w, top_panel_h),
            2,
        )

        # Health bar
        bar_w, bar_h = 220, 18
        hp_ratio = max(0, player.hp / player.max_hp)
        pygame.draw.rect(
            screen, (50, 50, 50), (screen_x + 18, screen_y + 18, bar_w, bar_h)
        )
        hp_col = (
            (50, 200, 50)
            if hp_ratio > 0.5
            else (220, 180, 30) if hp_ratio > 0.25 else (220, 40, 40)
        )
        pygame.draw.rect(
            screen,
            hp_col,
            (screen_x + 18, screen_y + 18, int(bar_w * hp_ratio), bar_h),
        )
        screen.blit(
            font_small.render(
                f"HP: {player.hp:.0f}/{player.max_hp}", True, (255, 255, 255)
            ),
            (screen_x + 25, screen_y + 20),
        )

        # XP bar
        xp_bar_w = 220
        xp_ratio = player.xp / player.xp_next if player.xp_next > 0 else 0
        pygame.draw.rect(
            screen, (50, 50, 0), (screen_x + 18, screen_y + 44, xp_bar_w, 10)
        )
        pygame.draw.rect(
            screen,
            (255, 255, 0),
            (screen_x + 18, screen_y + 44, int(xp_bar_w * xp_ratio), 10),
        )
        screen.blit(
            font_tiny.render(
                f"Lv {player.level}  XP: {player.xp}/{player.xp_next}",
                True,
                (255, 255, 0),
            ),
            (screen_x + 18, screen_y + 56),
        )

        # Current pickaxe
        pick = PICKAXES[player.pick_level]
        pygame.draw.rect(screen, pick["color"], (screen_x + 18, screen_y + 74, 10, 10))
        pick_label = (
            pick["name"]
            if player.pick_level < len(PICKAXES) - 1
            else f"{pick['name']} (MAX)"
        )
        screen.blit(
            font_tiny.render(pick_label, True, (255, 255, 255)),
            (screen_x + 32, screen_y + 73),
        )

        # Current weapon
        wpn_def = WEAPON_REGISTRY.get(player.weapon_id)
        if wpn_def is not None:
            pygame.draw.rect(
                screen, wpn_def.color, (screen_x + 18, screen_y + 90, 10, 10)
            )
            n_unlocked = len(player.unlocked_weapons)
            wpn_label = (
                f"{wpn_def.name} [{n_unlocked}]" if n_unlocked > 1 else wpn_def.name
            )
        else:
            pygame.draw.rect(
                screen, (100, 100, 100), (screen_x + 18, screen_y + 90, 10, 10)
            )
            wpn_label = "No weapon"
        screen.blit(
            font_tiny.render(wpn_label, True, (255, 150, 100)),
            (screen_x + 32, screen_y + 89),
        )

        # Defense %
        def_pct = int(player.defense_pct * 100)
        equip_key_name = pygame.key.name(player.controls.equip_key).upper()
        screen.blit(
            font_tiny.render(
                f"Defense: {def_pct}%  [{equip_key_name}] Inventory",
                True,
                (160, 220, 160),
            ),
            (screen_x + 18, screen_y + 108),
        )

        # Workers / pets
        parts: list[str] = []
        workers_here = [
            w
            for sc in game.maps.values()
            for w in sc.workers
            if getattr(w, "player_id", None) == player.player_id
        ]
        if workers_here:
            parts.append(f"Workers: {len(workers_here)}")
        pets_here = [
            p
            for sc in game.maps.values()
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
            screen.blit(
                font_tiny.render("  ".join(parts), True, (100, 220, 255)),
                (screen_x + 18, screen_y + 126),
            )

    # ------------------------------------------------------------------
    # Bottom controls panel
    # ------------------------------------------------------------------

    def _draw_bottom_panel(
        self,
        player: "Player",
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        game = self.game
        screen = game.screen
        font_small = game.font_ui_sm
        font_tiny = game.font_ui_xs

        bottom_panel_h = 130
        ctrl_y_start = screen_y + view_h - 138
        bottom_panel_w = 340
        bottom_panel_surf = pygame.Surface(
            (bottom_panel_w, bottom_panel_h), pygame.SRCALPHA
        )
        bottom_panel_surf.fill((20, 20, 30, 200))
        screen.blit(bottom_panel_surf, (screen_x + 8, ctrl_y_start))

        pygame.draw.rect(
            screen,
            (150, 150, 150),
            (screen_x + 8, ctrl_y_start, bottom_panel_w, bottom_panel_h),
            2,
        )

        # Control scheme (2-column layout)
        controls = player.controls.get_controls_list()

        ctrl_y = ctrl_y_start + 8
        ctrl_header = font_small.render("Controls:", True, (200, 200, 200))
        screen.blit(ctrl_header, (screen_x + 18, ctrl_y))

        controls_per_column = 3
        column_widths = [0, 90, 210]
        for idx, ctrl_text in enumerate(controls):
            col = idx // controls_per_column
            row = idx % controls_per_column
            x_offset = column_widths[col]
            y_offset = ctrl_y + 24 + row * 15
            ctrl_surf = font_tiny.render(ctrl_text, True, (180, 180, 180))
            screen.blit(ctrl_surf, (screen_x + 18 + x_offset, y_offset))

        # Auto-toggle status
        auto_y = ctrl_y + 24 + (controls_per_column - 1) * 15 + 20
        auto_mine_key = pygame.key.name(player.controls.toggle_auto_mine_key).upper()
        auto_mine_status = (
            f"Auto Mine ({auto_mine_key}): {'ON' if player.auto_mine else 'OFF'}"
        )
        auto_mine_color = (100, 255, 100) if player.auto_mine else (150, 150, 150)
        auto_mine_text = font_tiny.render(auto_mine_status, True, auto_mine_color)
        screen.blit(auto_mine_text, (screen_x + 18, auto_y))

        auto_fire_key = pygame.key.name(player.controls.toggle_auto_fire_key).upper()
        auto_fire_status = (
            f"Auto Fire ({auto_fire_key}): {'ON' if player.auto_fire else 'OFF'}"
        )
        auto_fire_color = (100, 255, 100) if player.auto_fire else (150, 150, 150)
        auto_fire_text = font_tiny.render(auto_fire_status, True, auto_fire_color)
        screen.blit(auto_fire_text, (screen_x + 18, auto_y + 16))

    # ------------------------------------------------------------------
    # Context-sensitive interaction hints
    # ------------------------------------------------------------------

    def _draw_interaction_hints(
        self,
        player: "Player",
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        game = self.game
        screen = game.screen
        font_tiny = game.font_ui_xs

        interact_key = pygame.key.name(player.controls.interact_key).upper()
        current_map_obj = game.get_player_current_map(player)
        if current_map_obj is None:
            return

        p_col = int(player.x) // TILE
        p_row = int(player.y) // TILE
        tile_id = current_map_obj.get_tile(p_row, p_col)

        hint_x_fn = lambda surf: screen_x + view_w // 2 - surf.get_width() // 2
        hint_y = screen_y + view_h - 150

        if tile_id in (CAVE_MOUNTAIN, CAVE_HILL):
            hint = font_tiny.render(
                f"[{interact_key}] Enter cave", True, (180, 180, 255)
            )
            screen.blit(hint, (hint_x_fn(hint), hint_y))
        elif tile_id == CAVE_EXIT:
            hint = font_tiny.render(
                f"[{interact_key}] Exit cave", True, (180, 255, 180)
            )
            screen.blit(hint, (hint_x_fn(hint), hint_y))
        elif tile_id == HOUSE and current_map_obj.tileset == "overland":
            cluster_size = current_map_obj.town_clusters.get((p_row, p_col), 1)
            _tier_idx, tier_name = _get_settlement_tier(cluster_size)
            hint = font_tiny.render(
                f"[{interact_key}] Enter {tier_name}", True, (255, 210, 130)
            )
            screen.blit(hint, (hint_x_fn(hint), hint_y))
        elif tile_id == SETTLEMENT_HOUSE:
            hint = font_tiny.render(
                f"[{interact_key}] Enter house", True, (255, 210, 130)
            )
            screen.blit(hint, (hint_x_fn(hint), hint_y))
        elif tile_id == HOUSE_EXIT:
            hint = font_tiny.render(f"[{interact_key}] Exit", True, (180, 255, 180))
            screen.blit(hint, (hint_x_fn(hint), hint_y))
        elif tile_id == WORKTABLE or any(
            current_map_obj.get_tile(p_row + dr, p_col + dc) == WORKTABLE
            for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]
        ):
            if game._is_in_housing_env(player):
                hint = font_tiny.render(
                    f"[{interact_key}] Craft", True, (130, 220, 255)
                )
                screen.blit(hint, (hint_x_fn(hint), hint_y))
        elif any(
            current_map_obj.get_tile(p_row + dr, p_col + dc) == SIGN
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]
        ):
            hint = font_tiny.render(
                f"[{interact_key}] Read sign", True, (230, 200, 120)
            )
            screen.blit(hint, (hint_x_fn(hint), hint_y))
        elif any(
            current_map_obj.get_tile(p_row + dr, p_col + dc) == BROKEN_LADDER
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]
        ):
            hint = font_tiny.render(
                f"[{interact_key}] Repair ladder", True, (200, 160, 90)
            )
            screen.blit(hint, (hint_x_fn(hint), hint_y))
        elif any(
            current_map_obj.get_tile(p_row + dr, p_col + dc) == SKY_LADDER
            for dc, dr in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]
        ):
            hint = font_tiny.render(
                f"[{interact_key}] Ascend to sky", True, (140, 200, 255)
            )
            screen.blit(hint, (hint_x_fn(hint), hint_y))

    # ------------------------------------------------------------------
    # Sector minimap (top-right corner)
    # ------------------------------------------------------------------

    def _draw_sector_minimap(
        self,
        player: "Player",
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        """Draw a small sector-grid minimap in the top-right corner."""
        game = self.game
        player_sector = game.sectors.get_player_sector(player)
        if player_sector is None:
            return

        screen = game.screen
        cx, cy = player_sector

        CELL = 10
        GAP = 1
        WINDOW = 9
        half = WINDOW // 2

        panel_w = WINDOW * (CELL + GAP) - GAP + 8
        panel_h = WINDOW * (CELL + GAP) - GAP + 8 + 14
        panel_x = screen_x + view_w - panel_w - 8
        panel_y = screen_y + 8

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((20, 20, 30, 200))
        screen.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(
            screen, (150, 150, 150), (panel_x, panel_y, panel_w, panel_h), 2
        )

        label = game.font_ui_xs.render("MAP", True, (180, 180, 180))
        screen.blit(
            label, (panel_x + panel_w // 2 - label.get_width() // 2, panel_y + 3)
        )

        grid_top = panel_y + 14 + 4

        for row in range(WINDOW):
            for col in range(WINDOW):
                sx = cx + (col - half)
                sy = cy + (row - half)

                cell_x = panel_x + 4 + col * (CELL + GAP)
                cell_y = grid_top + row * (CELL + GAP)

                if (sx, sy) in game.visited_sectors:
                    if (sx, sy) in game.land_sectors:
                        biome = get_sector_biome(game.world_seed, sx, sy)
                        color = {
                            BiomeType.STANDARD: (50, 110, 50),
                            BiomeType.TUNDRA: (120, 180, 220),
                            BiomeType.VOLCANO: (200, 70, 20),
                            BiomeType.ZOMBIE: (80, 95, 60),
                            BiomeType.DESERT: (195, 170, 85),
                        }.get(biome, (50, 110, 50))
                    else:
                        color = (35, 55, 110)
                elif (sx, sy) in game.sky_revealed_sectors:
                    if (sx, sy) in game.land_sectors:
                        color = (30, 65, 30)
                    else:
                        color = (20, 30, 60)
                else:
                    color = (25, 25, 35)

                pygame.draw.rect(screen, color, (cell_x, cell_y, CELL, CELL))

                if (sx, sy) in game.sky_revealed_sectors and (
                    sx,
                    sy,
                ) not in game.visited_sectors:
                    pygame.draw.rect(
                        screen, (60, 100, 160), (cell_x, cell_y, CELL, CELL), 1
                    )

                if sx == cx and sy == cy:
                    pygame.draw.rect(
                        screen, (220, 220, 255), (cell_x, cell_y, CELL, CELL), 2
                    )

        dot_x = panel_x + 4 + half * (CELL + GAP) + CELL // 2
        dot_y = grid_top + half * (CELL + GAP) + CELL // 2
        pygame.draw.circle(screen, (255, 255, 255), (dot_x, dot_y), 2)

    # ------------------------------------------------------------------
    # Sign text popup
    # ------------------------------------------------------------------

    def _draw_sign_display(
        self,
        player: "Player",
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        game = self.game
        pid = player.player_id
        disp = game._sign_display[pid]
        if disp is None:
            return

        screen = game.screen
        lines = disp["text"].split("\n")
        font = game.font_ui_sm
        line_h = font.get_height() + 4
        padding = 14
        panel_h = line_h * len(lines) + padding * 2
        panel_w = view_w - 80
        panel_x = screen_x + 40
        panel_y = screen_y + view_h - panel_h - 24

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((15, 10, 5, 210))
        pygame.draw.rect(
            panel_surf, (180, 140, 70), (0, 0, panel_w, panel_h), 2, border_radius=4
        )
        screen.blit(panel_surf, (panel_x, panel_y))

        for i, line in enumerate(lines):
            color = (230, 200, 130) if i == 0 else (210, 185, 145)
            rendered = font.render(line, True, color)
            screen.blit(rendered, (panel_x + padding, panel_y + padding + i * line_h))

    # ------------------------------------------------------------------
    # Sky ascend/descend flash overlay
    # ------------------------------------------------------------------

    def _draw_sky_anim_overlay(
        self,
        player: "Player",
        screen_x: int,
        screen_y: int,
        view_w: int,
        view_h: int,
    ) -> None:
        game = self.game
        pid = player.player_id
        anim = game._sky_anim[pid]
        if anim is None or anim["phase"] == "sky":
            return

        progress = anim["progress"]
        if anim["phase"] == "ascend":
            alpha = int(progress * 255)
        else:
            alpha = int((1.0 - progress) * 255)

        if alpha <= 0:
            return
        overlay = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, alpha))
        game.screen.blit(overlay, (screen_x, screen_y))


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _get_settlement_tier(cluster_size: int) -> tuple[int, str]:
    """Return (tier_index, tier_name) for a given cluster size."""
    for i in range(len(SETTLEMENT_TIER_SIZES) - 1, -1, -1):
        if cluster_size >= SETTLEMENT_TIER_SIZES[i]:
            return (i, SETTLEMENT_TIER_NAMES[i])
    return (0, SETTLEMENT_TIER_NAMES[0])
