# GameDevCopilot

一句话生成可运行的 Godot 游戏原型。输入自然语言，Agent 自主完成知识检索、代码生成、引擎无头验证与自动修复。

## 技术栈

- **Agent 工作流**：LangGraph（状态图）+ LangChain（LLM 调用）
- **LLM**：OpenAI 兼容接口（当前 deepseek-v4-flash），可切换
- **RAG**：bge-m3（本地 embedding）+ FAISS 向量检索，知识库 842 文本块
- **引擎验证**：Godot 4.7 无头模式（--headless），每次 <1s
- **前端**：FastAPI + Jinja2 + 原生 JS

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
├── web/                   # 网页 demo
├── docs/                  # 简历描述 + 面试讲解材料
└── tests/                 # 21 个单测
```

## 快速开始

```bash
# 1. 配置模型（.env）
cp .env.example .env
# 填入 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL

# 2. 生成一个游戏（输出到 outputs/）
.venv/Scripts/python.exe cli.py "做一个塔防游戏，敌人沿路走，放塔自动攻击"

# 3. LangGraph 工作流版
.venv/Scripts/python.exe cli.py "做一个平台跳跃游戏" --workflow

# 4. 网页 demo
.venv/Scripts/python.exe -m web.app
# 打开 http://127.0.0.1:8000

# 5. 跑测试
.venv/Scripts/python.exe -m pytest tests/
```

## 生成示例

输入「做一个塔防游戏」→ 产出 `outputs/` 下的完整 Godot 工程（project.godot + 场景 + 脚本），可用 Godot 编辑器打开运行。

## 核心流程

```
需求 → [类型检测: 命中骨架?] → [RAG 检索: 注入设计知识]
     → LangGraph: generate → normalize → verify ──通过──→ 产出
                                ↑        └──失败──→ fix (≤3轮)
```

## 环境要求

- Python 3.10+，venv（含 langchain-openai, langgraph, fastapi, FlagEmbedding, faiss-cpu）
- Godot 4.7（tools/ 下，需自行下载解压）
- bge-m3 模型（本地 models/bge-m3，用于 RAG）
