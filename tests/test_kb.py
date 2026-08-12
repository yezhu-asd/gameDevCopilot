from knowledge_base.kb import build_chunks, chunk_document


SAMPLE_DOC = {
    "source": "test.md",
    "title": "测试文档",
    "text": """# 测试文档

这是一个段落，用于测试分块逻辑。

## 第二个章节

这里是第二章的内容，应该被单独切成一块。

"重复的引用文字 " 用于验证去重。""" * 3,
}


def test_chunk_document_splits_sections():
    chunks = chunk_document(SAMPLE_DOC, size=200, overlap=20)
    assert len(chunks) >= 2, "长文档应该切成多块"
    assert all("text" in c and "source" in c for c in chunks)


def test_chunk_size_respected():
    chunks = chunk_document(SAMPLE_DOC, size=120, overlap=20)
    for c in chunks:
        assert len(c["text"]) <= 120, f"块超过 size 上限: {len(c['text'])}"


def test_build_chunks_loads_wiki_only():
    chunks = build_chunks()
    assert len(chunks) > 0
    sources = {c["source"] for c in chunks}
    # The compiled game-design wiki is the sole corpus.
    assert any("concepts/" in s for s in sources), "应该加载了 game-design-wiki 的 concepts"
    assert any("references/" in s for s in sources), "应该加载了 game-design-wiki 的 references"
    # 自写 guide 文档已移除，不应再加载。
    assert not any(s == "godot4_implementation.md" for s in sources)
