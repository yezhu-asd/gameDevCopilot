"""GameDevCopilot — one-line prompt to a playable Godot prototype.

CLI:
    python cli.py "做一个平台跳跃小游戏，有金币和敌人"
    python cli.py --example smoke   # run the fixed smoke test spec
    python cli.py --example roguelike   # run a sample spec
    python cli.py --out mygame     # output to project's outputs/mygame
    python cli.py --temp           # use a temp dir (default: outputs/ under project)
    python cli.py --workflow       # run via LangGraph workflow (default: linear pipeline)
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from core import config
from core.pipeline import cleanup, make_temp_output, run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUTS_DIR = config.PROJECT_ROOT / "outputs"

EXAMPLES = {
    "smoke": "做一个最小的 2D 游戏：一个可以 WASD 移动的方块，一个静态墙，碰到墙不会穿过。",
    "roguelike": "做一个极简 Roguelike：玩家用方向键移动，踩到怪物就战斗（随机胜负），吃掉宝箱得金币，死亡则结束。",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="GameDevCopilot")
    parser.add_argument("spec", nargs="?", help="自然语言游戏描述")
    parser.add_argument("--example", choices=list(EXAMPLES), help="运行内置示例需求")
    parser.add_argument("--out", type=Path, default=None, help="输出到项目 outputs/ 下的子目录")
    parser.add_argument("--temp", action="store_true", help="使用临时目录（不保留）")
    parser.add_argument("--workflow", action="store_true", help="用 LangGraph 工作流（默认线性 pipeline）")
    args = parser.parse_args()

    if args.example:
        spec = EXAMPLES[args.example]
    elif args.spec:
        spec = args.spec
    else:
        parser.print_help()
        return

    if not config.LLM_API_KEY:
        logger.error("未配置 LLM_API_KEY。请设置环境变量或在 .env 中配置。")
        return

    # Default: keep results under project's outputs/. Only --temp goes to tmp.
    use_temp = args.temp or not (args.spec or args.example)
    if args.out:
        out_root = OUTPUTS_DIR / args.out
    elif not use_temp:
        out_root = OUTPUTS_DIR / _slugify(spec)
    else:
        out_root = make_temp_output()

    logger.info("需求: %s", spec)
    logger.info("输出目录: %s", out_root)

    if args.workflow:
        from core.workflow import run_workflow

        logger.info("运行模式: LangGraph 工作流")
        result = run_workflow(spec, out_root)
    else:
        logger.info("运行模式: 线性 pipeline")
        result = run_pipeline(spec, out_root)

    for run in result.runs:
        status = "✅ 通过" if run.passed else f"❌ {run.result.error_count} 错误"
        logger.info("第 %d 轮(%s): %s", run.attempt, run.action, status)

    if result.success:
        logger.info("🎮 生成成功: %s", result.final_dir)
        logger.info("可用 Godot 编辑器打开 %s 运行，或用 --headless 再次验证。", result.final_dir)
    else:
        logger.error("生成失败（%d 轮未通过）。最近错误: %s", result.rounds_used, result.last_errors[:3])

    if use_temp:
        logger.info("清理临时目录（用 --out 保留到项目 outputs/ 下）")
        cleanup(out_root)


def _slugify(text: str) -> str:
    """Turn a Chinese spec into a short, safe directory name."""
    import re
    cleaned = re.sub(r"[^\w一-鿿]+", "_", text).strip("_")
    return cleaned[:24] or "game"


if __name__ == "__main__":
    main()
