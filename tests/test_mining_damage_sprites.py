"""Tests for mining damage sprite system."""

from __future__ import annotations

import json
import os

import pytest

from src.data.tiles import TILE_INFO

# ---------------------------------------------------------------------------
# Sprite sheet height limit
# ---------------------------------------------------------------------------

TILES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "tiles",
)
MAX_SHEET_HEIGHT = 8000


def _iter_atlas_manifests():
    """Yield (name, manifest_dict) for each atlas JSON in assets/tiles/."""
    for fname in sorted(os.listdir(TILES_DIR)):
        if fname.endswith(".json"):
            path = os.path.join(TILES_DIR, fname)
            with open(path) as f:
                yield fname, json.load(f)


class TestSpriteSheetLimits:
    """All generated atlas sheets must stay under 8000px tall."""

    @pytest.mark.parametrize(
        "name,manifest",
        list(_iter_atlas_manifests()),
        ids=[n for n, _ in _iter_atlas_manifests()],
    )
    def test_sheet_height_under_limit(self, name: str, manifest: dict) -> None:
        cell_h = manifest["cell_size"][1]
        tiles = manifest["tiles"]
        if not tiles:
            return
        max_row = max(t["start_row"] for t in tiles.values())
        total_rows = max_row + 16  # 16 adjacency variants per tile
        height = total_rows * cell_h
        assert (
            height <= MAX_SHEET_HEIGHT
        ), f"{name}: sheet height {height}px exceeds {MAX_SHEET_HEIGHT}px limit"


# ---------------------------------------------------------------------------
# No stale unsplit sheets
# ---------------------------------------------------------------------------


class TestNoStaleSheets:
    """Old unsplit atlas files must not exist."""

    @pytest.mark.parametrize(
        "stale_name",
        ["terrain_basic", "terrain_ore", "terrain_settlement"],
    )
    def test_no_stale_atlas(self, stale_name: str) -> None:
        for ext in (".png", ".json"):
            path = os.path.join(TILES_DIR, stale_name + ext)
            assert not os.path.exists(path), (
                f"Stale atlas {stale_name}{ext} still exists — should have been "
                f"replaced by {stale_name}_a / {stale_name}_b splits"
            )


# ---------------------------------------------------------------------------
# Damage frame index computation
# ---------------------------------------------------------------------------


def _damage_fidx(cur_hp: int, max_hp: int) -> int:
    """Replicate the render-loop damage frame computation."""
    if max_hp <= 0:
        return 0
    damage_pct = 1.0 - cur_hp / max_hp
    return min(3, int(damage_pct * 4))


class TestDamageFrameIndex:
    """Verify frame index maps HP percentage to the correct damage column."""

    def test_full_hp_is_frame_0(self) -> None:
        assert _damage_fidx(100, 100) == 0

    def test_slight_damage_still_frame_0(self) -> None:
        # 90% HP → damage_pct 0.10 → int(0.40) = 0
        assert _damage_fidx(90, 100) == 0

    def test_75pct_hp_is_frame_1(self) -> None:
        # 75% HP → damage_pct 0.25 → int(1.0) = 1
        assert _damage_fidx(75, 100) == 1

    def test_50pct_hp_is_frame_2(self) -> None:
        # 50% HP → damage_pct 0.50 → int(2.0) = 2
        assert _damage_fidx(50, 100) == 2

    def test_25pct_hp_is_frame_3(self) -> None:
        # 25% HP → damage_pct 0.75 → int(3.0) = 3
        assert _damage_fidx(25, 100) == 3

    def test_1_hp_is_frame_3(self) -> None:
        # Nearly dead → capped at 3
        assert _damage_fidx(1, 100) == 3

    def test_0_hp_is_frame_3(self) -> None:
        # Fully depleted → capped at 3 (tile about to break)
        assert _damage_fidx(0, 100) == 3

    def test_zero_max_hp_returns_0(self) -> None:
        assert _damage_fidx(0, 0) == 0


# ---------------------------------------------------------------------------
# Coral FPS should be 0 (damage states, not animation)
# ---------------------------------------------------------------------------


class TestCoralFps:
    """Coral must be static (fps=0) so frame columns are damage states."""

    def test_coral_fps_zero_in_manifests(self) -> None:
        for name, manifest in _iter_atlas_manifests():
            tiles = manifest.get("tiles", {})
            if "coral" in tiles:
                assert (
                    tiles["coral"]["fps"] == 0.0
                ), f"Coral in {name} has fps={tiles['coral']['fps']}, expected 0"


# ---------------------------------------------------------------------------
# All mineable tiles must have fps=0 in their atlas
# ---------------------------------------------------------------------------


class TestMineableTilesFpsZero:
    """Mineable tiles should have fps==0 so their 4 columns are damage states."""

    def test_mineable_tiles_are_static(self) -> None:
        # Build a set of tile names that are mineable
        from tools.bake_tile_sprites import TILE_NAMES

        mineable_names: set[str] = set()
        for tid, name in TILE_NAMES.items():
            info = TILE_INFO.get(tid, {})
            if info.get("mineable"):
                mineable_names.add(name)

        # Check every atlas manifest
        for manifest_name, manifest in _iter_atlas_manifests():
            tiles = manifest.get("tiles", {})
            for tname, tdata in tiles.items():
                if tname in mineable_names:
                    assert tdata["fps"] == 0.0, (
                        f"{tname} in {manifest_name} has fps={tdata['fps']}, "
                        f"but mineable tiles must be static (fps=0)"
                    )
