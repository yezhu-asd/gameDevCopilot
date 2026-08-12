"""Game-type template skeletons: detect genre from a spec and render the
verified-working skeleton so the LLM fills in gameplay instead of building
the project structure from scratch.

Skeletons live under templates/<genre>/ and are verified headless.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Keyword sets per genre. Order matters: first match wins.
GENRES = [
    {
        "name": "tower_defense",
        "aliases": ["塔防", "塔防游戏", "放塔", "防御塔", "tower defense", "tower defence"],
        "keywords": ["塔", "敌人", "路径", "金币", "放塔", "防守"],
    },
    {
        "name": "platformer",
        "aliases": ["平台跳跃", "跳跃", "跑酷", "platformer", "jump"],
        "keywords": ["跳跃", "金币", "平台", "地面", "关卡"],
    },
    {
        "name": "roguelike",
        "aliases": ["roguelike", "Roguelike", "爬塔", "随机生成", "永久死亡"],
        "keywords": ["随机", "怪物", "宝箱", "生命", "网格", "死亡"],
    },
]


def detect_genre(spec: str) -> str | None:
    """Return the best-matching genre name, or None if no template fits."""
    spec_l = spec.lower()
    for genre in GENRES:
        for alias in genre["aliases"]:
            if alias.lower() in spec_l:
                return genre["name"]
    # Fallback: score by keyword overlap.
    best_name, best_score = None, 0
    for genre in GENRES:
        score = sum(1 for k in genre["keywords"] if k in spec_l)
        if score > best_score:
            best_name, best_score = genre["name"], score
    return best_name if best_score >= 2 else None


def load_template_files(genre: str) -> dict[str, str]:
    """Load a skeleton's files as {path: content}."""
    genre_dir = TEMPLATES_DIR / genre
    files: dict[str, str] = {}
    if not genre_dir.exists():
        logger.warning("模板目录不存在: %s", genre_dir)
        return files
    for path in sorted(genre_dir.rglob("*")):
        if path.is_file() and path.suffix in {".gd", ".tscn", ".godot"}:
            rel = path.relative_to(genre_dir).as_posix()
            files[rel] = path.read_text(encoding="utf-8")
    return files


def render_template(spec: str) -> tuple[str | None, str]:
    """If spec matches a genre, return (genre, prompt text) describing the skeleton.

    The prompt tells the model to fill gameplay on top of the given skeleton
    rather than regenerate the project scaffolding.
    """
    genre = detect_genre(spec)
    if genre is None:
        return None, ""
    files = load_template_files(genre)
    if not files:
        return genre, ""
    block = "\n\n".join(f"### {path}\n```\n{content}\n```" for path, content in files.items())
    prompt = (
        f"\n\n===== {genre} 骨架（已验证可运行，必须在此骨架上填充，不要重新设计项目结构）=====\n"
        "下面的文件构成一个最小可运行原型。请在保持文件结构、节点名、信号、方法签名不变的前提下，"
        "根据用户需求填充/扩展玩法（数值、敌人、收集物、关卡等）。可以新增 .gd/.tscn 文件，"
        "但不要改动骨架中已有的 main.tscn 的根节点与 main.gd 的入口方法。\n\n"
        + block
    )
    logger.info("[template] 命中 %s 骨架模板", genre)
    return genre, prompt
