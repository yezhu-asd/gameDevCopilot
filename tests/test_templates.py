from core.templates import detect_genre, load_template_files, render_template


def test_detect_platformer():
    assert detect_genre("做一个平台跳跃游戏，空格跳跃") == "platformer"


def test_detect_tower_defense():
    assert detect_genre("做一个塔防游戏，放塔打敌人") == "tower_defense"


def test_detect_roguelike():
    assert detect_genre("做一个 Roguelike 爬塔游戏") == "roguelike"


def test_detect_unknown_returns_none():
    assert detect_genre("做一个毫无特征的游戏") is None


def test_load_template_files_has_key_files():
    files = load_template_files("platformer")
    assert "project.godot" in files
    assert "main.tscn" in files
    assert "main.gd" in files


def test_render_template_injects_skeleton():
    genre, prompt = render_template("做一个塔防游戏")
    assert genre == "tower_defense"
    assert "main.gd" in prompt
    assert "骨架" in prompt


def test_render_template_none_for_unknown():
    genre, prompt = render_template("做一个毫无特征的游戏")
    assert genre is None
    assert prompt == ""
