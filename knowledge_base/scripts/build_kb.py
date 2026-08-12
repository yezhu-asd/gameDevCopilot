"""Build the game-design knowledge base index from markdown docs.

Usage:
    python -m knowledge_base.scripts.build_kb
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from knowledge_base.kb import build_index  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    result = build_index()
    print(f"\n知识库构建完成：{result['chunks']} 个文本块，向量维度 {result['dim']}")
    print("索引已保存到 knowledge_base/index/")


if __name__ == "__main__":
    main()
