from core.pipeline import GODOT3_TO_4, normalize_files
from core.verifier import _check_godot3_apis


def test_staticbody2d_is_not_flagged():
    """Valid StaticBody2D must not be mistaken for Godot 3 StaticBody."""
    files = {
        "main.tscn": '[node name="Ground" type="StaticBody2D" parent="."]',
        "player.gd": "extends CharacterBody2D",
    }
    issues = _check_godot3_apis(files)
    assert issues == [], f"StaticBody2D 不应被误报: {issues}"


def test_bare_staticbody_is_flagged_and_normalized():
    """Bare StaticBody (Godot 3) must be flagged and rewritten to StaticBody2D."""
    files = {"main.tscn": '[node name="Ground" type="StaticBody" parent="."]'}
    issues = _check_godot3_apis(files)
    assert any("StaticBody" in i for i in issues), "裸 StaticBody 应被静态检查报出"

    normalized = normalize_files(files)
    assert "StaticBody2D" in normalized["main.tscn"]
    assert "StaticBody2D2D" not in normalized["main.tscn"], "不能把 StaticBody2D 再改写一次"


def test_kinematicbody2d_not_double_rewritten():
    files = {"player.gd": "extends KinematicBody2D"}
    normalized = normalize_files(files)
    assert "CharacterBody2D" in normalized["player.gd"]
    assert "CharacterBody2D2D" not in normalized["player.gd"]


def test_godot3_to_4_regex_compiled():
    for pattern in GODOT3_TO_4:
        assert hasattr(pattern, "search"), "规范化规则必须是编译好的正则"
