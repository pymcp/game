"""Animation state machine for sprite-sheet based entity rendering.

Each Animator instance owns a reference to a loaded sprite sheet and a
manifest that describes which row / column range corresponds to each named
animation state.

Manifest JSON schema
--------------------
{
  "frame_size": [width, height],
  "states": {
    "<state_name>": {
      "row":    <int>,      // 0-based row index in the sheet
      "frames": <int>,      // number of columns (frames) in this state
      "fps":    <float>     // playback speed in real frames-per-second
    },
    ...
  }
}

The sheet is laid out as rows (states) × columns (frames).  All cells in a
sheet share the same (width × height) dimensions from ``frame_size``.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    pass


class AnimationState(Enum):
    """Named animation states an entity can be in."""

    IDLE = "idle"
    WALK = "walk"
    SWIM = "swim"
    HURT = "hurt"
    MOUNTED = "mounted"


class Animator:
    """Frame-rate-independent sprite animator driven by game ``dt`` values.

    ``dt`` is the normalised frame delta used throughout the codebase:
        dt = clock.tick(FPS) / 16.667
    so dt ≈ 1.0 at 60 fps.  Internally this is converted to milliseconds
    (ms = dt × 16.667) so that the per-state ``fps`` value in the manifest
    translates directly to real-world playback speed.

    Falls back gracefully: if the current state has no entry in the manifest
    ``current_frame()`` returns ``None`` (caller should use procedural draw).
    """

    def __init__(self, sheet: pygame.Surface, manifest: dict) -> None:
        self._sheet = sheet
        self._manifest = manifest
        fw, fh = manifest["frame_size"]
        self._fw: int = fw
        self._fh: int = fh

        self._state: AnimationState = AnimationState.IDLE
        self._frame_idx: int = 0
        self._elapsed_ms: float = 0.0

    # ------------------------------------------------------------------
    # State control
    # ------------------------------------------------------------------

    def set_state(self, state: AnimationState) -> None:
        """Switch to *state* and reset frame counter if state changed."""
        if state == self._state:
            return
        # Only switch if the new state actually exists in the manifest;
        # otherwise keep the current state (avoids falling to None mid-game).
        if state.value in self._manifest["states"] or self._state_data(state) is not None:
            self._state = state
            self._frame_idx = 0
            self._elapsed_ms = 0.0

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance animation by *dt* game-frames (≈1.0 at 60 fps)."""
        data = self._state_data(self._state)
        if data is None or data["frames"] <= 1:
            return

        fps: float = data.get("fps", 8.0)
        frame_duration_ms: float = 1000.0 / fps
        self._elapsed_ms += dt * 16.667

        if self._elapsed_ms >= frame_duration_ms:
            self._elapsed_ms -= frame_duration_ms
            self._frame_idx = (self._frame_idx + 1) % data["frames"]

    # ------------------------------------------------------------------
    # Read current frame
    # ------------------------------------------------------------------

    def current_frame(self) -> pygame.Surface | None:
        """Return the current frame surface, or *None* if state is unknown."""
        data = self._state_data(self._state)
        if data is None:
            # Try fallback to IDLE
            data = self._state_data(AnimationState.IDLE)
        if data is None:
            # Last resort: use whichever state exists first in the manifest
            data = next(iter(self._manifest["states"].values()), None)
        if data is None:
            return None

        row: int = data["row"]
        col: int = self._frame_idx % max(1, data["frames"])
        rect = pygame.Rect(col * self._fw, row * self._fh, self._fw, self._fh)
        try:
            return self._sheet.subsurface(rect)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _state_data(self, state: AnimationState) -> dict | None:
        return self._manifest["states"].get(state.value)
