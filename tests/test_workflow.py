"""Unit tests for the LangGraph workflow using mocked LLM calls."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FakeModel:
    """A stub model that returns canned file sets on request."""

    def __init__(self):
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        # First call: valid project (passes). Subsequent: same.
        return type("R", (), {"content": _GOOD_PROJECT})()


_GOOD_PROJECT = """### project.godot
```
config_version=5

[application]

config/name="Test"
run/main_scene="res://main.tscn"
config/features=PackedStringArray("4.7", "2D")

[rendering]

renderer/rendering_method="gl_compatibility"
```

### main.tscn
```
[gd_scene load_steps=3 format=3]

[node name="Main" type="Node2D"]
```

### main.gd
```gdscript
extends Node2D
```
"""


@pytest.fixture
def out_root(tmp_path):
    return tmp_path / "runs"


def test_graph_generates_and_passes(out_root):
    from core.workflow import run_workflow

    fake = FakeModel()
    result = run_workflow("做个测试游戏", out_root, model=fake, max_rounds=2)
    assert result.success
    assert result.final_dir.exists()
    assert result.rounds_used == 1  # one generate, no fix
    assert fake.calls == 1


class FailOnceModel:
    """First generate emits a script with a Godot 3 API; fix returns valid."""

    def __init__(self):
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            # A .tscn that references an undefined sub_resource -> real Godot error.
            broken = _GOOD_PROJECT.replace(
                "### main.gd\n```gdscript\nextends Node2D\n```",
                """### main.tscn
```
[gd_scene load_steps=3 format=3]

[node name="Main" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]
shape = SubResource("missing_shape")
```
""",
            )
            return type("R", (), {"content": broken})()
        return type("R", (), {"content": _GOOD_PROJECT})()


def test_graph_fixes_broken_generation(out_root):
    from core.workflow import run_workflow

    fake = FailOnceModel()
    result = run_workflow("做个测试游戏", out_root, model=fake, max_rounds=2)
    assert result.success
    assert result.rounds_used == 2  # generate failed -> fix passed
    assert fake.calls == 2


def test_graph_stops_when_rounds_exhausted(out_root):
    from core.workflow import run_workflow

    class AlwaysFailModel:
        def invoke(self, messages):
            # A tscn that references a sub_resource never defined -> hard error.
            broken = _GOOD_PROJECT.replace(
                "### main.gd\n```gdscript\nextends Node2D\n```",
                """### main.tscn
```
[gd_scene load_steps=3 format=3]

[sub_resource type="RectangleShape2D" id="shape"]
size = Vector2(40, 40)

[node name="Main" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]
shape = SubResource("missing_shape")
```
""",
            )
            return type("R", (), {"content": broken})()

    result = run_workflow("做个测试游戏", out_root, model=AlwaysFailModel(), max_rounds=1)
    assert not result.success
    assert result.rounds_used == 2  # 1 generate + 1 fix, then exhausted
