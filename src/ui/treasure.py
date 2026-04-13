"""Treasure chest loot and reveal popup.

Extracted from game.py — owns reveal state, loot logic, and overlay rendering.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from src.effects import Particle

if TYPE_CHECKING:
    from src.entities.player import Player


class TreasureManager:
    """Manages treasure chest opening, loot distribution, and reveal popups.

    Owns ``reveals`` list of active reveal popups.
    """

    def __init__(self, game: object) -> None:
        self.game = game
        self.reveals: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_chest(self, player: "Player", tx: int, ty: int) -> None:
        """Award loot from a treasure chest, spawn particles, and queue a reveal popup."""
        loot: dict[str, int] = {"Sail": 1}
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

        # Dramatic particle burst
        sparkle_colors = [
            (255, 230, 80),
            (255, 200, 40),
            (255, 255, 160),
            (255, 255, 255),
            (255, 180, 60),
        ]
        for _ in range(55):
            p = Particle(tx, ty, random.choice(sparkle_colors), player.current_map)
            angle = random.uniform(-math.pi, 0)
            speed = random.uniform(2, 6)
            p.vx = math.cos(angle) * speed
            p.vy = math.sin(angle) * speed
            p.life = random.randint(25, 50)
            p.size = random.randint(2, 5)
            self.game.particles.append(p)
        for _ in range(12):
            p = Particle(tx, ty, (200, 140, 40), player.current_map)
            p.life = random.randint(10, 20)
            p.size = random.randint(3, 6)
            self.game.particles.append(p)

        self.reveals.append(
            {
                "player_id": player.player_id,
                "items": loot,
                "timer": 180.0,
            }
        )

    def tick(self, dt: float = 1.0) -> None:
        """Advance reveal timers and cull expired entries."""
        for reveal in self.reveals:
            reveal["timer"] -= dt
        self.reveals[:] = [r for r in self.reveals if r["timer"] > 0]

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
        """Draw the treasure chest loot popup for a player's viewport."""
        reveal = next(
            (r for r in self.reveals if r["player_id"] == player.player_id),
            None,
        )
        if reveal is None:
            return

        screen = self.game.screen
        alpha = int(min(255, reveal["timer"] / 60 * 255))
        alpha = max(0, min(255, alpha))

        items = reveal["items"]
        item_count = len(items)

        panel_w = max(280, item_count * 90 + 40)
        panel_h = 100
        panel_x = screen_x + view_w // 2 - panel_w // 2
        panel_y = screen_y + view_h // 2 - panel_h // 2 - 40

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((30, 20, 0, min(220, alpha)))
        screen.blit(panel_surf, (panel_x, panel_y))
        border_col = (220, 180, 40, alpha)
        border_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(border_surf, border_col, (0, 0, panel_w, panel_h), 3)
        screen.blit(border_surf, (panel_x, panel_y))

        font_med = self.game.font_dc_med
        font_sm = self.game.font_dc_sm
        header = font_med.render("\u2726 TREASURE! \u2726", True, (255, 220, 60))
        header.set_alpha(alpha)
        screen.blit(
            header,
            (panel_x + panel_w // 2 - header.get_width() // 2, panel_y + 6),
        )

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
            screen.blit(txt, (ix, item_y))
            ix += txt.get_width() + 16
