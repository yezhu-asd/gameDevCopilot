from core.pipeline import normalize_tscn


def test_normalize_tscn_reorders_ext_resources():
    messy = """[gd_scene load_steps=4 format=3]

[sub_resource type="RectangleShape2D" id="player_shape"]
size = Vector2(40, 40)

[ext_resource type="Script" path="res://player.gd" id="1_player"]

[node name="Main" type="Node2D"]
"""
    fixed = normalize_tscn(messy)
    ext_pos = fixed.index("[ext_resource")
    sub_pos = fixed.index("[sub_resource")
    assert ext_pos < sub_pos, "ext_resource must come before sub_resource"
    assert fixed.index("[node name=\"Main\"") > sub_pos


def test_normalize_tscn_noop_when_ordered():
    good = """[gd_scene load_steps=4 format=3]

[ext_resource type="Script" path="res://player.gd" id="1_player"]

[sub_resource type="RectangleShape2D" id="player_shape"]
size = Vector2(40, 40)

[node name="Main" type="Node2D"]
"""
    assert normalize_tscn(good) == good


def test_normalize_tscn_noop_without_subs():
    plain = """[gd_scene format=3]

[node name="Main" type="Node2D"]
"""
    assert normalize_tscn(plain) == plain
