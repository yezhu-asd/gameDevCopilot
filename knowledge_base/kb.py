"""Game-design knowledge base: build and search a vector index over the docs.

Pipeline: markdown docs -> text chunks -> bge-m3 embeddings -> FAISS index.
The built index (chunks.json + faiss.bin) is saved under knowledge_base/index/.

Corpus scanned:
  - rag/game-design-wiki/wiki/  the compiled game-design wiki (concepts/references/topics)
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = PROJECT_ROOT / "rag" / "game-design-wiki" / "wiki"
INDEX_DIR = PROJECT_ROOT / "knowledge_base" / "index"
CHUNKS_FILE = INDEX_DIR / "chunks.json"
INDEX_FILE = INDEX_DIR / "faiss.bin"

# bge-m3 模型路径：优先环境变量 BGE_MODEL_DIR，回退到项目内 models/bge-m3
BGE_MODEL_DIR = Path(os.getenv("BGE_MODEL_DIR", PROJECT_ROOT / "models" / "bge-m3"))
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


# ---------------------------------------------------------------- chunking ---
def load_docs() -> list[dict]:
    """Load every markdown doc from the docs dir and the game-design wiki.

    Each doc is {source, title, category, summary, text}. YAML frontmatter is
    parsed when present; the summary is prepended to the text so chunks carry
    the doc's thesis even when the body is long.
    """
    docs: list[dict] = []

    for md in sorted(WIKI_DIR.rglob("*.md")):
        if "_index.md" in md.name:
            continue
        raw = md.read_text(encoding="utf-8")
        meta, body = _split_frontmatter(raw)
        title = meta.get("title") or _first_heading(body) or md.stem
        summary = meta.get("summary", "")
        category = meta.get("category", "wiki")
        docs.append({
            "source": str(md.relative_to(WIKI_DIR)).replace("\\", "/"),
            "title": title,
            "category": category,
            "summary": summary,
            "text": body,
        })

    logger.info("loaded %d wiki docs", len(docs))
    return docs


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body) for a markdown file with --- fences."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    return meta, text[m.end():]


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return ""


def chunk_document(doc: dict, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split a document into overlapping chunks. Split on section headings first,
    then by sentence/paragraph, then hard-cut at `size` characters.
    """
    chunks: list[dict] = []
    body = doc["text"]
    # Prepend the summary so even long sections carry the doc's thesis.
    text = f"[摘要] {doc['summary']}\n\n{body}" if doc.get("summary") else body

    # Split into sections by markdown headings.
    sections = re.split(r"(?=^#{2,4}\s)", text, flags=re.MULTILINE)

    for section in sections:
        section = section.strip()
        if not section:
            continue
        # Further split long sections into paragraph-sized pieces.
        pieces = re.split(r"\n\s*\n", section)
        buffer = ""
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            if len(buffer) + len(piece) + 1 <= size:
                buffer = f"{buffer}\n\n{piece}".strip()
            else:
                if buffer:
                    chunks.append(_make_chunk(doc, buffer))
                # Split over-long paragraphs by character.
                while len(piece) > size:
                    chunks.append(_make_chunk(doc, piece[:size]))
                    piece = piece[size - overlap:]
                buffer = piece
        if buffer:
            chunks.append(_make_chunk(doc, buffer))

    return chunks


def _make_chunk(doc: dict, text: str) -> dict:
    return {
        "source": doc["source"],
        "title": doc["title"],
        "category": doc.get("category", ""),
        "text": text,
    }


def build_chunks() -> list[dict]:
    """Load docs and chunk them into a flat list."""
    docs = load_docs()
    chunks: list[dict] = []
    for doc in docs:
        chunks.extend(chunk_document(doc))
    logger.info("chunked %d docs into %d chunks", len(docs), len(chunks))
    return chunks


# --------------------------------------------------------------- embeddings ---
_embedder = None


def get_embedder():
    """Lazily load the bge-m3 model (kept in memory after first use).

    Returns None if the model directory is missing, so callers can degrade
    gracefully (skip RAG) instead of crashing on a missing local model.
    """
    global _embedder
    if _embedder is not None:
        return _embedder
    if not BGE_MODEL_DIR.exists():
        logger.warning("bge-m3 模型不存在（%s），RAG 将降级为纯 LLM 生成", BGE_MODEL_DIR)
        _embedder = False
        return None
    from FlagEmbedding import BGEM3FlagModel

    logger.info("loading bge-m3 from %s ...", BGE_MODEL_DIR)
    _embedder = BGEM3FlagModel(str(BGE_MODEL_DIR), use_fp16=False, device="cpu")
    logger.info("bge-m3 loaded")
    return _embedder


def embed_texts(texts: list[str], batch: int = 32) -> list[list[float]]:
    """Embed a list of texts with bge-m3, returning dense vectors."""
    model = get_embedder()
    if not model:  # None or False (unavailable)
        raise RuntimeError("bge-m3 模型不可用，无法向量化")
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch):
        chunk = texts[i:i + batch]
        result = model.encode(chunk, max_length=512)
        vectors.extend(v.tolist() for v in result["dense_vecs"])
    return vectors


# ------------------------------------------------------------------- build ---
def build_index() -> dict:
    """Chunk docs, embed them, and persist a FAISS index + metadata."""
    import numpy as np

    import faiss

    chunks = build_chunks()
    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)
    matrix = np.array(vectors, dtype="float32")

    dim = matrix.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(matrix)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_FILE))
    CHUNKS_FILE.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("saved index: %d chunks, dim=%d -> %s", len(chunks), dim, INDEX_DIR)
    return {"chunks": len(chunks), "dim": dim}


# ------------------------------------------------------------------ search ---
def search(query: str, top_k: int = 3) -> list[dict]:
    """Return the top_k most similar chunks for a query."""
    import numpy as np

    import faiss

    if not INDEX_FILE.exists() or not CHUNKS_FILE.exists():
        raise FileNotFoundError(
            f"知识库索引不存在，请先运行 build_index(): {INDEX_DIR}"
        )

    index = faiss.read_index(str(INDEX_FILE))
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))

    if not get_embedder():
        logger.warning("bge-m3 模型不可用，跳过检索")
        return []
    query_vec = np.array(embed_texts([query]), dtype="float32")
    scores, idxs = index.search(query_vec, min(top_k, len(chunks)))

    results = []
    for score, idx in zip(scores[0], idxs[0]):
        if idx < 0:
            continue
        results.append({**chunks[idx], "score": round(float(score), 4)})
    return results


def format_context(results: list[dict], max_chars: int = 3000) -> str:
    """Render retrieved chunks as prompt-ready context."""
    parts = []
    used = 0
    for r in results:
        tag = f" [{r['category']}]" if r.get("category") else ""
        block = f"### [{r['source']}]{tag} {r['title']}\n{r['text']}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts)
