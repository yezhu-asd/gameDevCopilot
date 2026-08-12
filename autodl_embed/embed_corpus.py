#!/usr/bin/env python3
"""
AutoDL 向量化脚本 — 把语料转成 bge-m3 向量，输出 .npy 文件供本地 FAISS 索引使用。

用法:
    conda activate 你的环境        # AutoDL 镜像通常自带 python
    pip install -r requirements.txt
    python embed_corpus.py

输出（在当前目录）:
    embeddings.npy    float32 [N, 1024]  每个文本块的向量
    chunks.json       与向量一一对应的文本块元数据（source/title/text）
    log.txt           运行日志

在 AutoDL 上运行前请把 models/ 里的 bge-m3 模型和 corpus/ 语料一并上传。
"""
from __future__ import annotations

import json
import logging
import re
import os
import sys
import time
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent
CORPUS_DIR = BASE_DIR / "corpus"
# 模型路径优先级：环境变量 BGE_MODEL_DIR > 默认 AutoDL 路径 > 打包目录 models/bge-m3
# AutoDL 上默认的 bge 模型位置（已确认存在）：
AUTODL_MODEL_DIR = Path("/root/autodl-tmp/embedding_pipeline/models/bge-m3")
MODEL_DIR = Path(
    os.environ.get("BGE_MODEL_DIR", AUTODL_MODEL_DIR)
)
OUT_EMB = BASE_DIR / "embeddings.npy"
OUT_CHUNKS = BASE_DIR / "chunks.json"
BATCH = 64

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(BASE_DIR / "log.txt", encoding="utf-8")],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- frontmatter ---
def split_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    return meta, text[m.end():]


# ------------------------------------------------------------------- chunk ---
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


def load_docs() -> list[dict]:
    docs = []
    # wiki docs（concepts/references/topics）
    for md in sorted(CORPUS_DIR.glob("wiki/**/*.md")):
        if "_index.md" in md.name:
            continue
        raw = md.read_text(encoding="utf-8")
        meta, body = split_frontmatter(raw)
        title = meta.get("title") or next((l.lstrip("# ").strip() for l in body.splitlines() if l.startswith("#")), md.stem)
        docs.append({
            "source": str(md.relative_to(CORPUS_DIR)).replace("\\", "/"),
            "title": title,
            "summary": meta.get("summary", ""),
            "text": body,
        })
    return docs


def chunk_document(doc: dict) -> list[dict]:
    chunks = []
    text = f"[摘要] {doc['summary']}\n\n{doc['text']}" if doc.get("summary") else doc["text"]
    sections = re.split(r"(?=^#{2,4}\s)", text, flags=re.MULTILINE)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        pieces = re.split(r"\n\s*\n", section)
        buffer = ""
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            if len(buffer) + len(piece) + 1 <= CHUNK_SIZE:
                buffer = f"{buffer}\n\n{piece}".strip()
            else:
                if buffer:
                    chunks.append({"source": doc["source"], "title": doc["title"], "text": buffer})
                while len(piece) > CHUNK_SIZE:
                    chunks.append({"source": doc["source"], "title": doc["title"], "text": piece[:CHUNK_SIZE]})
                    piece = piece[CHUNK_SIZE - CHUNK_OVERLAP:]
                buffer = piece
        if buffer:
            chunks.append({"source": doc["source"], "title": doc["title"], "text": buffer})
    return chunks


# --------------------------------------------------------------- embed ---
def main() -> None:
    if not MODEL_DIR.exists():
        logger.error("模型目录不存在: %s （请把 bge-m3 模型放到 models/ 下）", MODEL_DIR)
        sys.exit(1)

    t0 = time.time()
    from FlagEmbedding import BGEM3FlagModel

    logger.info("加载 bge-m3: %s", MODEL_DIR)
    model = BGEM3FlagModel(str(MODEL_DIR), use_fp16=False, device="cpu")

    docs = load_docs()
    logger.info("加载 %d 篇文档", len(docs))
    chunks = []
    for d in docs:
        chunks.extend(chunk_document(d))
    logger.info("切分为 %d 个文本块", len(chunks))
    texts = [c["text"] for c in chunks]

    all_vecs = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i:i + BATCH]
        result = model.encode(batch, max_length=512)
        all_vecs.append(np.array(result["dense_vecs"], dtype="float32"))
        logger.info("进度 %d/%d", min(i + BATCH, len(texts)), len(texts))

    emb = np.concatenate(all_vecs, axis=0)
    np.save(OUT_EMB, emb)
    OUT_CHUNKS.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    logger.info("完成！embeddings.npy shape=%s, chunks=%d, 用时 %.1fs", emb.shape, len(chunks), time.time() - t0)


if __name__ == "__main__":
    main()
