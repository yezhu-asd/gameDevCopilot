"""LLM calls for the generate-fix loop."""
from __future__ import annotations

import logging
import os

from core import config
from core.templates import render_template

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个资深 Godot 4.x 游戏开发工程师，负责生成可运行的游戏原型。

输出格式（严格遵守）：用 markdown 文件块列出一组文件。每个文件块以 `### 文件名` 开头，紧跟一个代码块：

### project.godot
```
config_version=5
...
```

### main.tscn
```
[gd_scene load_steps=4 format=3]
...
```

规则：
1. 每个文件块标题为 `### 文件名`，下一行是代码块。文件名必须唯一。
2. 必须包含 project.godot 和主场景文件（如 main.tscn），project.godot 的 run/main_scene 指向主场景。
3. 项目必须能在无头模式下正常加载并运行 5 秒不报错（脚本无语法错误、资源引用完整、类型匹配）。
4. 使用 Godot 4.x API 和 GDScript。碰撞形状用 sub_resource 定义，不要用子节点挂 shape。
5. 每个 .gd 脚本用 path 指向实际位置，节点类型必须与脚本继承类型匹配。
6. 如果用户描述了具体玩法，请实现核心玩法逻辑；无法保证的复杂玩法可以简化，但要保证可运行。
7. 场景文件必须使用 Godot 4 的 tscn 文本格式（[gd_scene ...] 开头），绝不是 XML 或 JSON。

这是一个 Godot 4 项目的最小示例，场景格式和资源引用方式必须严格照此：
### project.godot
```
config_version=5

[application]

config/name="MyGame"
run/main_scene="res://main.tscn"
config/features=PackedStringArray("4.7", "2D")

[rendering]

renderer/rendering_method="gl_compatibility"
```

### main.tscn
```
[gd_scene load_steps=4 format=3]

[ext_resource type="Script" path="res://player.gd" id="1_player"]

[sub_resource type="RectangleShape2D" id="player_shape"]
size = Vector2(40, 40)

[node name="Main" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]
position = Vector2(200, 300)
script = ExtResource("1_player")

[node name="CollisionShape2D" type="CollisionShape2D" parent="Player"]
shape = SubResource("player_shape")
```

### player.gd
```gdscript
extends CharacterBody2D

const SPEED := 300.0

func _physics_process(_delta: float) -> void:
	var input_dir := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	velocity = input_dir * SPEED
	move_and_slide()
```
"""

FIX_SYSTEM_PROMPT = """你是 Godot 专家，负责修复生成的 Godot 项目中的错误。
根据运行日志中的错误信息，用与生成时相同的 markdown 文件块格式，输出修正后的完整文件集合。
修复后必须解决日志中的全部错误。不要输出任何其他内容。"""


def _resolve_llm():
    if config.MODEL_PROVIDER == "azure":
        from langchain_openai import AzureChatOpenAI
        return AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            api_version=os.getenv("AZURE_OPENAI_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            temperature=0,
        )
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.LLM_API_KEY,
        base_url=config.LLM_BASE_URL,
        temperature=0,
    )


def generate_project(spec: str, model=None, use_rag: bool = True, on_phase=None) -> dict:
    """Generate a full Godot project as {path: content} for a natural-language spec.

    When use_rag is True, retrieves relevant game-design docs from the knowledge
    base and injects them into the system prompt as grounding context. When the
    spec matches a genre template, the verified skeleton is injected so the
    model fills in gameplay instead of rebuilding scaffolding.

    `on_phase` is an optional callable(phase: str) called at phase boundaries
    ("rag", "generating") so callers can surface progress.
    """
    def _phase(name: str) -> None:
        if on_phase is not None:
            on_phase(name)

    llm = model or _resolve_llm()
    system = SYSTEM_PROMPT
    if use_rag:
        _phase("rag")
        context = _retrieve_context(spec)
        if context:
            system = (
                SYSTEM_PROMPT
                + "\n\n===== 游戏设计知识库参考（严格遵循其中与本需求相关的实现要点）=====\n"
                + context
            )
    _, template_prompt = render_template(spec)
    if template_prompt:
        system += template_prompt
    _phase("generating")
    response = llm.invoke(
        [{"role": "system", "content": system}, {"role": "user", "content": spec}]
    )
    return _parse_files(response.content)


def _retrieve_context(spec: str, top_k: int = 3) -> str:
    """Retrieve relevant knowledge-base chunks for a spec. No-op if no index."""
    try:
        from knowledge_base.kb import format_context, search
    except Exception as exc:  # index missing or deps unavailable
        logger.info("RAG 不可用，跳过知识检索: %s", exc)
        return ""
    try:
        results = search(spec, top_k=top_k)
    except FileNotFoundError:
        logger.info("知识库索引不存在，跳过 RAG")
        return ""
    if not results:
        return ""
    context = format_context(results)
    logger.info("RAG 检索到 %d 条知识（涉及 %s）", len(results), sorted({r['source'] for r in results}))
    return context


def fix_project(spec: str, errors: list[str], current: dict, model=None) -> dict:
    """Ask the model to repair a failing project given the error log."""
    llm = model or _resolve_llm()
    error_block = "\n".join(errors)
    payload = f"原始需求：{spec}\n\n当前文件：\n{_dump_files(current)}\n\n运行错误：\n{error_block}"
    response = llm.invoke(
        [
            {"role": "system", "content": FIX_SYSTEM_PROMPT},
            {"role": "user", "content": payload},
        ]
    )
    return _parse_files(response.content)


def _dump_files(files: dict) -> str:
    return "\n\n".join(f"### {path}\n```\n{content}\n```" for path, content in files.items())


def _parse_files(raw: str) -> dict:
    """Parse markdown file blocks into {path: content}.

    Format: lines of `### <path>` followed by a ``` code block.
    """
    import re

    files: dict[str, str] = {}
    # Match a heading line plus the code block that follows.
    pattern = re.compile(r"^###\s+(.+?)\s*\n```(?:[a-zA-Z0-9_-]*)?\n(.*?)\n```", re.DOTALL | re.MULTILINE)
    matches = pattern.findall(raw)
    if matches:
        for path, content in matches:
            path = path.strip()
            if path:
                files[path] = content
        if files:
            return files
    # Fallback: tolerate a JSON reply (some models still emit JSON).
    return _parse_files_json(raw)


def _parse_files_json(raw: str) -> dict:
    """Fallback parser for a JSON reply: {"files": {...}} or flat {path: content}."""
    import json
    import re

    text = raw.strip()
    fenced = re.match(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Model reply was not a JSON object: " + raw[:200])
    files = data.get("files", data)
    if not isinstance(files, dict):
        raise ValueError("'files' must be a dict of path -> content")
    return {str(path): _to_text(content) for path, content in files.items()}


def _to_text(value) -> str:
    if isinstance(value, str):
        return value
    import json
    return json.dumps(value, ensure_ascii=False)
