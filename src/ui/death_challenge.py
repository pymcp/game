"""Death challenge — math problem respawn mechanic.

Extracted from game.py — owns challeng state, input handling, respawn logic,
and the overlay rendering.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pygame

from src.config import GRASS, TILE, WORLD_COLS, WORLD_ROWS
from src.effects import FloatingText

if TYPE_CHECKING:
    from src.entities.player import Player


class DeathChallengeManager:
    """Manages per-player death challenges (math problems to respawn).

    Owns ``challenges`` dict keyed by player_id.
    """

    def __init__(self, game: object) -> None:
        self.game = game
        self.challenges: dict[int, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_active(self, player_id: int) -> bool:
        return player_id in self.challenges

    def start(self, player: "Player") -> None:
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
        self.challenges[player.player_id] = {
            "question": question,
            "answer": answer,
            "input": "",
            "wrong": False,
        }

    def submit(self, player: "Player") -> None:
        """Check the typed answer; respawn player on correct answer."""
        challenge = self.challenges.get(player.player_id)
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
            del self.challenges[player.player_id]
            self._respawn(player)
            self.game.floats.append(
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

    def handle_keydown(self, key: int, player: "Player") -> bool:
        """Handle a keydown for an active death challenge.

        Returns True if the key was consumed, False if it should propagate.
        """
        challenge = self.challenges.get(player.player_id)
        if challenge is None:
            return False

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
            return True
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS) and not challenge["input"]:
            challenge["input"] = "-"
            challenge["wrong"] = False
            return True
        elif key == pygame.K_BACKSPACE:
            challenge["input"] = challenge["input"][:-1]
            challenge["wrong"] = False
            return True
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.submit(player)
            return True
        return False

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
        """Draw the death/respawn math challenge overlay for a player's viewport."""
        challenge = self.challenges.get(player.player_id)
        if challenge is None:
            return

        screen = self.game.screen
        overlay = pygame.Surface((view_w, view_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (screen_x, screen_y))

        font_big = self.game.font_dc_big
        font_med = self.game.font_dc_med
        font_small = self.game.font_dc_sm

        cx = screen_x + view_w // 2
        cy = screen_y + view_h // 2

        panel_w, panel_h = 360, 210
        panel_x = cx - panel_w // 2
        panel_y = cy - panel_h // 2

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((20, 10, 10, 235))
        screen.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(screen, (200, 50, 50), (panel_x, panel_y, panel_w, panel_h), 3)

        died_surf = font_big.render("YOU DIED", True, (255, 50, 50))
        screen.blit(died_surf, (cx - died_surf.get_width() // 2, panel_y + 14))

        desc_surf = font_small.render(
            "Solve to respawn at full health:", True, (200, 200, 200)
        )
        screen.blit(desc_surf, (cx - desc_surf.get_width() // 2, panel_y + 62))

        q_surf = font_med.render(challenge["question"], True, (255, 255, 100))
        screen.blit(q_surf, (cx - q_surf.get_width() // 2, panel_y + 88))

        input_display = challenge["input"] if challenge["input"] else "_"
        input_color = (255, 80, 80) if challenge.get("wrong") else (100, 255, 100)
        input_surf = font_med.render(input_display, True, input_color)
        screen.blit(input_surf, (cx - input_surf.get_width() // 2, panel_y + 130))

        if challenge.get("wrong"):
            hint_surf = font_small.render(
                "Wrong answer — try again!", True, (255, 80, 80)
            )
        else:
            hint_surf = font_small.render(
                "Type your answer and press Enter", True, (140, 140, 140)
            )
        screen.blit(hint_surf, (cx - hint_surf.get_width() // 2, panel_y + 175))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _respawn(self, player: "Player") -> None:
        """Teleport a respawning player to a safe grass tile near the world centre."""
        if (
            player.last_portal_exit_map is not None
            and player.last_portal_exit_x is not None
            and player.last_portal_exit_map in self.game.maps
        ):
            player.current_map = player.last_portal_exit_map
            player.x = player.last_portal_exit_x
            player.y = player.last_portal_exit_y
            self.game._snap_camera_to_player(player)
            return
        player.current_map = "overland"
        overland = self.game.maps["overland"]
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
