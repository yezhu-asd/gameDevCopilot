# GameDevCopilot

一句话生成可运行的 Godot 游戏原型。输入自然语言，Agent 自主完成知识检索、代码生成、引擎无头验证与自动修复，最终产出一个**真正能运行**的 Godot 游戏。

```
需求 → [类型检测: 命中骨架?] → [RAG 检索: 注入设计知识]
     → LangGraph: generate → normalize → verify ──通过──→ 产出可运行游戏
                                ↑        └──失败──→ fix (≤3轮)
```

## 技术栈

| 模块 | 技术 |
|---|---|
| Agent 工作流 | LangGraph（状态图）+ LangChain |
| LLM | OpenAI 兼容接口（DeepSeek / 智谱 / 通义等，可切换） |
| RAG 知识库 | bge-m3 本地 embedding + FAISS 向量检索（842 文本块） |
| 引擎验证 | Godot 4.7 无头模式（`--headless`），单次 <1s |
| 前端 | FastAPI + Jinja2 + 原生 JS |
| 测试 | pytest（21 个单测） |

---

## 部署

### 1. 克隆仓库

```bash
git clone https://github.com/yezhu-asd/gameDevCopilot.git
cd gameDevCopilot
```

### 2. 准备 Python 环境

需要 **Python 3.10+**。创建虚拟环境并安装依赖：

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

> `requirements.txt` 不存在时，安装以下核心依赖：
> `langchain-openai langgraph fastapi uvicorn python-dotenv FlagEmbedding faiss-cpu numpy pytest`

### 3. 下载 Godot 引擎

`tools/` 已被 gitignore（二进制太大），需自行下载 Godot **4.x**：

1. 到 [Godot 官网](https://godotengine.org/download/) 下载 Windows/Linux/macOS 版
2. 解压后把可执行文件放到 `tools/` 目录下，重命名为：

| 平台 | 路径 |
|---|---|
| Windows | `tools/Godot_v4.7.1-stable_win64.exe` |
| macOS/Linux | `tools/godot` |

> 默认路径在 `core/config.py` 的 `GODOT_EXE`，如用其他文件名请同步修改。

### 4. 准备 bge-m3 模型（RAG 用）

从 HuggingFace 下载 [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3)，放到项目内：

```
models/bge-m3/
```

> 默认读取项目内 `models/bge-m3`。若模型在别处，在 `.env` 里设置 `BGE_MODEL_DIR` 指向绝对路径。

### 5. 配置 LLM

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 LLM 配置（详见 `.env.example` 内注释）：

```ini
MODEL_PROVIDER=openai-compatible
LLM_API_KEY=你的_API_KEY
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

### 6. 构建知识库索引

首次使用需要把语料向量化并建索引：

```bash
# 方式一：本地构建（CPU，约 2 分钟，语料 74 篇）
.venv/Scripts/python.exe -m knowledge_base.scripts.build_kb

# 方式二：AutoDL GPU 加速（推荐，快）
#   1. 上传 autodl_embed/ 到 AutoDL
#   2. 运行 python embed_corpus.py（参考 autodl_embed/README.md）
#   3. 下载 embeddings.npy + chunks.json 到 autodl_embed/results/
#   4. 本地跑：
.venv/Scripts/python.exe -m knowledge_base.scripts.build_index_from_emb
```

索引生成到 `knowledge_base/index/`（gitignore，不随仓库分发）。

### 7. 验证部署

```bash
# 跑测试（不含 LLM 的单元测试）
.venv/Scripts/python.exe -m pytest tests/ --ignore=tests/test_smoke.py
```

---

## 使用

### CLI 生成游戏

```bash
# 生成一个游戏（默认线性 pipeline，输出到 outputs/）
.venv/Scripts/python.exe cli.py "做一个塔防游戏，敌人沿路走，放塔自动攻击"

# 用 LangGraph 工作流版
.venv/Scripts/python.exe cli.py "做一个平台跳跃游戏" --workflow

# 指定输出目录
.venv/Scripts/python.exe cli.py "做一个贪吃蛇游戏" --out snake

# 使用临时目录（不保留）
.venv/Scripts/python.exe cli.py "..." --temp
```

运行内置示例：

```bash
.venv/Scripts/python.exe cli.py --example smoke      # 最小移动+碰撞
.venv/Scripts/python.exe cli.py --example roguelike  # 极简 Roguelike
```

生成的游戏在 `outputs/<需求名>/attempt_*` 下，取**数字最大的目录**（最后成功的版本）。

### 打开生成的游戏

用 Godot 打开生成目录里的 `project.godot`：

```bash
# Windows
tools/Godot_v4.7.1-stable_win64.exe --path "outputs/做一个塔防游戏.../attempt_gen_0"

# 或双击 tools/ 下的 Godot，点"导入"，选中 project.godot
```

打开后按 **F5** 运行。也可用无头模式再验证一次：

```bash
tools/Godot_v4.7.1-stable_win64.exe --headless --path "outputs/<你的游戏>/attempt_gen_0" --quit-after 5
```

### 网页 Demo

启动 Web 服务（依赖 LLM 配置 + 知识库索引）：

```bash
.venv/Scripts/python.exe -m web.app
```

浏览器打开 **http://127.0.0.1:8000**：
- 输入一句话 → 点击"生成游戏"
- 实时查看：RAG 检索 → Agent 生成 → Godot 无头验证 → 自动修复 → 完成
- 完成后可查看生成的代码文件

---

## 目录结构

```
game_dev_copilot/
├── cli.py                 # 命令行入口
├── core/
│   ├── config.py          # 配置（模型、路径、轮次）
│   ├── pipeline.py        # 线性生成-验证-修复循环（含进度回调）
│   ├── workflow.py        # LangGraph 状态图版本
│   ├── verifier.py        # Godot 无头验证 + 静态 API 检查
│   └── templates.py       # 游戏类型检测 + 骨架注入
├── agents/
│   └── coder.py           # LLM 生成/修复 + RAG 上下文注入
├── knowledge_base/
│   ├── kb.py              # 分块/embedding/检索
│   └── scripts/           # 索引构建
├── templates/             # 三类已验证骨架（platformer/roguelike/tower_defense）
├── rag/                   # game-design-wiki 语料（74 篇）
├── autodl_embed/          # AutoDL 向量化打包
├── web/                   # 网页 demo
├── docs/                  # 简历描述 + 面试讲解材料
└── tests/                 # 21 个单测
```

## 环境要求

- Python 3.10+
- Godot 4.x（需自行下载到 `tools/`）
- bge-m3 模型（RAG 需要）
- 可用的 LLM API（OpenAI 兼容接口）
