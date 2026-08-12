"""Build the FAISS index from AutoDL-generated embeddings.

Reads embeddings.npy + chunks.json produced by autodl_embed/embed_corpus.py and
writes the FAISS index + metadata into knowledge_base/index/.

Usage:
    python -m knowledge_base.scripts.build_index_from_emb

    Expects autodl_embed/results/embeddings.npy and chunks.json (see README).
"""
import json
import logging
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import faiss  # noqa: E402

from knowledge_base.kb import INDEX_DIR, INDEX_FILE, CHUNKS_FILE  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RESULTS_DIR = PROJECT_ROOT / "autodl_embed" / "results"


def main() -> None:
    emb_path = RESULTS_DIR / "embeddings.npy"
    chunks_path = RESULTS_DIR / "chunks.json"
    if not emb_path.exists() or not chunks_path.exists():
        logger.error(
            "找不到 %s 或 %s。\n"
            "请先在 AutoDL 上运行 autodl_embed/embed_corpus.py，并把两个输出文件下载到 autodl_embed/results/ 下。",
            emb_path, chunks_path,
        )
        sys.exit(1)

    matrix = np.load(emb_path)
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    if len(matrix) != len(chunks):
        logger.error("向量数 %d 与文本块数 %d 不一致", len(matrix), len(chunks))
        sys.exit(1)

    dim = matrix.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(matrix.astype("float32"))

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_FILE))
    CHUNKS_FILE.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("索引构建完成：%d 个文本块，维度 %d -> %s", len(chunks), dim, INDEX_DIR)


if __name__ == "__main__":
    main()
