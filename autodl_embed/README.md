# AutoDL 向量化打包说明

把本文件夹上传到 AutoDL 后，用 GPU 把语料转成 bge-m3 向量，再把结果拿回本地构建 FAISS 索引。

## 文件夹内容

```
autodl_embed/
├── corpus/                # 语料（已打包：game-design-wiki 74 篇）
│   └── wiki/              # game-design-wiki（concepts / references / topics）
├── embed_corpus.py        # 向量化脚本
├── requirements.txt       # 依赖
└── README.md              # 本文件
```

**模型不打进包里**——直接用你 AutoDL 上已有的 bge 模型（见下文）。

## 操作步骤

### 1. 上传到 AutoDL

把整个 `autodl_embed/` 上传到 AutoDL（用 JupyterLab 上传，或 `scp` / FileZilla）。建议路径：`/root/autodl-tmp/autodl_embed`。

### 2. 在 AutoDL 上运行

打开 JupyterLab → 终端，执行：

```bash
cd /root/autodl-tmp/autodl_embed
pip install FlagEmbedding        # 缺什么装什么，numpy/torch 镜像自带
python embed_corpus.py
```

脚本默认使用 `/root/autodl-tmp/embedding_pipeline/models/bge-m3`（你 AutoDL 上已有的模型），**无需再指定路径**。若模型位置不同，可用环境变量覆盖：

```bash
export BGE_MODEL_DIR=/你的/实际/模型路径
```

运行期间会打印进度到 `log.txt`。结束后生成两个文件：

```
autodl_embed/
├── embeddings.npy    # 所有文本块的向量 [N, 1024]
└── chunks.json       # 与向量一一对应的文本块（source/title/text）
```

### 3. 下载结果回本地

把 `embeddings.npy` 和 `chunks.json` 下载到本地：

```
E:\wu\xidian\job\java\agent\game_dev_copilot\autodl_embed\results\
```

### 4. 在本地构建 FAISS 索引

运行本地脚本，用下载的向量构建索引（不需要再向量化，秒级完成）：

```bash
cd E:\wu\xidian\job\java\agent\game_dev_copilot
.venv\Scripts\python.exe -m knowledge_base.scripts.build_index_from_emb
```

索引会生成到 `knowledge_base/index/`，之后 RAG 直接可用。

## 常见问题

- **模型路径**：脚本默认用 `/root/autodl-tmp/embedding_pipeline/models/bge-m3`；若位置不同，设环境变量 `BGE_MODEL_DIR` 覆盖。
- **模型加载慢**：bge-m3 约 4.3G，CPU 首次加载 1-2 分钟，GPU 快很多。
- **内存不足**：74 篇文档约 200 个文本块，远小于 1G，AutoDL 默认内存足够。
- **改了语料**：只需重跑 `python embed_corpus.py`，重新下载两个文件 + 本地重建索引。
- **为什么不在本地向量化**：CPU 跑 82 篇文档要 5-10 分钟，GPU 只要 1 分钟；且 AutoDL 有 GPU 就顺手用上。
