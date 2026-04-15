"""Tests for save/load round-trip and schema migration."""

import json
import os
import pytest
from types import SimpleNamespace

from src.config import TILE
from src.save import (
    SAVE_VERSION,
    _run_migrations,
    _serialize_player,
    _deserialize_player,
    _serialize_map,
    _deserialize_map,
    _key_to_str,
    _str_to_key,
    save_game,
    load_game,
    apply_save,
    SAVE_PATH,
    SAVE_DIR,
)
from src.entities.player import CONTROL_SCHEME_PLAYER1, CONTROL_SCHEME_PLAYER2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_v10_dict() -> dict:
    """Minimal v10-era save dict (no 'objects' key in maps)."""
    return {
        "version": 10,
        "world_seed": 99,
        "maps": {
            "overland": {
                "tiles": [[1] * 20 for _ in range(20)],
                "biome": "grassland",
                "workers": [],
                "pets": [],
                "enemies": [],
                "creatures": [],
            }
        },
        "entity_archive": {},
        "players": [
            {
                "x": 640.0,
                "y": 640.0,
                "player_id": 1,
                "color": [100, 150, 200],
                "pick_level": 1,
                "weapon_id": "wooden_sword",
                "unlocked_weapons": ["wooden_sword"],
                "inventory": {},
                "hp": 100,
                "max_hp": 100,
                "xp": 0,
                "level": 1,
                "xp_next": 100,
                "facing_dx": 1,
                "facing_dy": 0,
                "auto_mine": False,
                "auto_fire": False,
                "on_boat": False,
                "boat_col": 0,
                "boat_row": 0,
                "current_map": "overland",
                "portal_origin_map": None,
                "last_portal_exit_map": None,
                "last_portal_exit_x": 0.0,
                "last_portal_exit_y": 0.0,
                "is_dead": False,
                "equipment": {"helmet": None, "chest": None, "legs": None, "boots": None},
                "durability": {},
                "on_mount": False,
            },
            {
                "x": 704.0,
                "y": 640.0,
                "player_id": 2,
                "color": [200, 150, 100],
                "pick_level": 1,
                "weapon_id": "wooden_sword",
                "unlocked_weapons": ["wooden_sword"],
                "inventory": {},
                "hp": 100,
                "max_hp": 100,
                "xp": 0,
                "level": 1,
                "xp_next": 100,
                "facing_dx": 1,
                "facing_dy": 0,
                "auto_mine": False,
                "auto_fire": False,
                "on_boat": False,
                "boat_col": 0,
                "boat_row": 0,
                "current_map": "overland",
                "portal_origin_map": None,
                "last_portal_exit_map": None,
                "last_portal_exit_x": 0.0,
                "last_portal_exit_y": 0.0,
                "is_dead": False,
                "equipment": {"helmet": None, "chest": None, "legs": None, "boots": None},
                "durability": {},
                "on_mount": False,
            },
        ],
        "visited_sectors": [[0, 0]],
        "land_sectors": [[0, 0]],
        "sky_revealed_sectors": [],
        "portal_quests": {},
    }


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


class TestRunMigrations:
    def test_v10_migrates_to_current(self) -> None:
        data = _make_v10_dict()
        result = _run_migrations(data)
        assert result is not None
        assert result["version"] == SAVE_VERSION

    def test_already_current_version_is_unchanged(self) -> None:
        data = {"version": SAVE_VERSION, "world_seed": 1}
        result = _run_migrations(data)
        assert result is not None
        assert result["version"] == SAVE_VERSION
        assert result["world_seed"] == 1

    def test_unknown_old_version_returns_none(self) -> None:
        data = {"version": 5, "world_seed": 1}
        result = _run_migrations(data)
        assert result is None

    def test_migration_preserves_other_fields(self) -> None:
        data = _make_v10_dict()
        data["world_seed"] = 777
        result = _run_migrations(data)
        assert result is not None
        assert result["world_seed"] == 777


# ---------------------------------------------------------------------------
# Key codec tests
# ---------------------------------------------------------------------------


class TestKeyCodec:
    def test_overland_roundtrip(self) -> None:
        assert _str_to_key(_key_to_str("overland")) == "overland"

    def test_sector_roundtrip(self) -> None:
        key = ("sector", 3, -1)
        assert _str_to_key(_key_to_str(key)) == key

    def test_cave_roundtrip(self) -> None:
        key = (5, 7)
        assert _str_to_key(_key_to_str(key)) == key

    def test_underwater_roundtrip(self) -> None:
        key = ("underwater", 2, 4)
        assert _str_to_key(_key_to_str(key)) == key


# ---------------------------------------------------------------------------
# Player serialization roundtrip
# ---------------------------------------------------------------------------


class TestPlayerSerializationRoundtrip:
    def test_basic_fields_preserved(self, player1: "Player") -> None:
        from src.entities.player import Player

        data = _serialize_player(player1)
        restored = _deserialize_player(data, CONTROL_SCHEME_PLAYER1)

        assert restored.x == player1.x
        assert restored.y == player1.y
        assert restored.player_id == player1.player_id
        assert restored.hp == player1.hp
        assert restored.max_hp == player1.max_hp
        assert restored.level == player1.level

    def test_inventory_preserved(self, player1: "Player") -> None:
        player1.inventory["Wood"] = 10
        player1.inventory["Stone"] = 5

        data = _serialize_player(player1)
        restored = _deserialize_player(data, CONTROL_SCHEME_PLAYER1)

        assert restored.inventory.get("Wood") == 10
        assert restored.inventory.get("Stone") == 5

    def test_on_mount_always_false_after_roundtrip(self, player1: "Player") -> None:
        player1.on_mount = True
        data = _serialize_player(player1)
        assert data["on_mount"] is False

    def test_equipment_preserved(self, player1: "Player") -> None:
        player1.equipment["helmet"] = "Iron Helmet"
        data = _serialize_player(player1)
        restored = _deserialize_player(data, CONTROL_SCHEME_PLAYER1)
        assert restored.equipment["helmet"] == "Iron Helmet"

    def test_xp_and_pick_level_preserved(self, player1: "Player") -> None:
        player1.xp = 250
        player1.pick_level = 3
        data = _serialize_player(player1)
        restored = _deserialize_player(data, CONTROL_SCHEME_PLAYER1)
        assert restored.xp == 250
        assert restored.pick_level == 3


# ---------------------------------------------------------------------------
# Map serialization roundtrip
# ---------------------------------------------------------------------------


class TestMapSerializationRoundtrip:
    def test_tile_data_preserved(self, mock_game_map: "GameMap") -> None:
        original_tile = mock_game_map.world[2][3]
        data = _serialize_map(mock_game_map)
        scene = _deserialize_map(data)
        restored_map = object.__getattribute__(scene, "map")
        assert restored_map.world[2][3] == original_tile

    def test_empty_entity_lists(self, mock_game_map: "GameMap") -> None:
        data = _serialize_map(mock_game_map)
        scene = _deserialize_map(data)
        assert list(scene.workers) == []
        assert list(scene.pets) == []

    def test_result_is_map_scene(self, mock_game_map: "GameMap") -> None:
        from src.world.scene import MapScene

        data = _serialize_map(mock_game_map)
        result = _deserialize_map(data)
        assert isinstance(result, MapScene)


# ---------------------------------------------------------------------------
# Full save / load roundtrip
# ---------------------------------------------------------------------------


class TestSaveLoadRoundtrip:
    def test_roundtrip_restores_world_seed(
        self, mock_game: "MockGame", tmp_path: pytest.TempPathFactory
    ) -> None:
        import src.save as save_mod

        # Patch save path to tmp dir
        orig_dir = save_mod.SAVE_DIR
        orig_path = save_mod.SAVE_PATH
        tmp_save = str(tmp_path / "save.json")
        save_mod.SAVE_DIR = str(tmp_path)
        save_mod.SAVE_PATH = tmp_save

        try:
            mock_game._entity_archive = mock_game.sectors._entity_archive
            mock_game.world_seed = 12345
            save_game(mock_game)
            assert os.path.exists(tmp_save)
            data = load_game()
            assert data is not None
            assert data["world_seed"] == 12345
        finally:
            save_mod.SAVE_DIR = orig_dir
            save_mod.SAVE_PATH = orig_path

    def test_roundtrip_restores_player_positions(
        self, mock_game: "MockGame", tmp_path: pytest.TempPathFactory
    ) -> None:
        import src.save as save_mod

        orig_dir = save_mod.SAVE_DIR
        orig_path = save_mod.SAVE_PATH
        tmp_save = str(tmp_path / "save.json")
        save_mod.SAVE_DIR = str(tmp_path)
        save_mod.SAVE_PATH = tmp_save

        try:
            mock_game._entity_archive = mock_game.sectors._entity_archive
            mock_game.player1.x = 100.0
            mock_game.player1.y = 200.0
            save_game(mock_game)
            data = load_game()
            assert data is not None
            assert data["players"][0]["x"] == 100.0
            assert data["players"][0]["y"] == 200.0
        finally:
            save_mod.SAVE_DIR = orig_dir
            save_mod.SAVE_PATH = orig_path

    def test_save_version_is_current(
        self, mock_game: "MockGame", tmp_path: pytest.TempPathFactory
    ) -> None:
        import src.save as save_mod

        orig_dir = save_mod.SAVE_DIR
        orig_path = save_mod.SAVE_PATH
        tmp_save = str(tmp_path / "save.json")
        save_mod.SAVE_DIR = str(tmp_path)
        save_mod.SAVE_PATH = tmp_save

        try:
            mock_game._entity_archive = mock_game.sectors._entity_archive
            save_game(mock_game)
            with open(tmp_save) as f:
                raw = json.load(f)
            assert raw["version"] == SAVE_VERSION
        finally:
            save_mod.SAVE_DIR = orig_dir
            save_mod.SAVE_PATH = orig_path

    def test_load_returns_none_when_no_file(self, tmp_path: pytest.TempPathFactory) -> None:
        import src.save as save_mod

        orig_dir = save_mod.SAVE_DIR
        orig_path = save_mod.SAVE_PATH
        save_mod.SAVE_DIR = str(tmp_path)
        save_mod.SAVE_PATH = str(tmp_path / "nonexistent.json")

        try:
            assert load_game() is None
        finally:
            save_mod.SAVE_DIR = orig_dir
            save_mod.SAVE_PATH = orig_path

    def test_load_returns_none_on_corrupt_json(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        import src.save as save_mod

        orig_dir = save_mod.SAVE_DIR
        orig_path = save_mod.SAVE_PATH
        tmp_save = str(tmp_path / "save.json")
        save_mod.SAVE_DIR = str(tmp_path)
        save_mod.SAVE_PATH = tmp_save

        try:
            with open(tmp_save, "w") as f:
                f.write("not valid json {{{{")
            assert load_game() is None
        finally:
            save_mod.SAVE_DIR = orig_dir
            save_mod.SAVE_PATH = orig_path
