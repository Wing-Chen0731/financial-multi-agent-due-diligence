# 金融多智能体系统（LangGraph）

这是一个按路线图落地的可运行骨架：`supervisor → data_collector → risk_analyzer → compliance_checker → report_writer`。它把任务分类、客户资料边界、知识库检索、风险提示和报告汇总放进同一张 LangGraph 状态图中。

## PTA 项目架构映射

```text
1 个智能中枢：Supervisor
1 个工具网关：ToolGateway（白名单 + 审计轨迹，可接远程 MCP）
N 个垂直 Agent：Data Collector / Risk Analyzer / Compliance Checker / Report Writer
N 个业务 Skill：授信尽调 / 合规知识 / 财务指标 / 行业新闻 / 金融安全护栏
```

行业新闻当前使用本地演示数据，实际接入时应替换为经过授权的新闻源；CRM 同样是模拟边界，不代表真实银行生产系统。

现在已经补充了一个面向展示的 Web 工作台：打开首页即可输入问题、运行分析、查看 Agent trace、置信度、人工复核标记和知识库来源。作品定位、演示脚本和后续生产化差距见 [PORTFOLIO.md](PORTFOLIO.md)。

完整的逐步试用说明见 [操作手册.md](操作手册.md)。

## 模型选择与速度策略

- **无模型演示模式**：`LLM_PROVIDER=demo`，无需 API key，适合先验收工作流或在同学电脑上快速查看作品。
- **本地开源模型（推荐）**：安装 [Ollama](https://ollama.com/)，使用约 1.4GB 的 `qwen3:1.7b`，将 `LLM_PROVIDER=ollama`。Embedding 使用 `qwen3-embedding:0.6b`，不需要购买 API Key。
- **远程开源模型（同学无需下载本地模型）**：使用 OpenRouter 或 Hugging Face Inference Providers 的 OpenAI-compatible 接口。远程模型仍需要每位使用者自己的 API Key，免费模型通常有额度、速率和可用性限制。
- **OpenAI-compatible API**：也可配置 DeepSeek 等服务，将 `LLM_PROVIDER=openai_compatible`、`OPENAI_API_KEY` 和 `OPENAI_BASE_URL` 写入环境文件。

### 同学开箱即用：远程模式

如果目标是“同学不安装 Ollama、不下载 8B 模型，直接打开作品”，推荐使用远程模式：

```bash
./scripts/start_remote.sh
# 第一次运行会生成 .env.remote，然后填入自己的 OPENROUTER_API_KEY，再运行一次
```

Windows PowerShell：

```powershell
.\scripts\start_remote.ps1
```

默认配置是 `LLM_PROVIDER=openrouter`、`LLM_MODEL=openrouter/free`，只调用远程聊天模型，不会在本机下载大模型。也可以把 `.env.remote` 改成 Hugging Face：

```dotenv
LLM_PROVIDER=huggingface
HF_TOKEN=你的_token
LLM_MODEL=你在 Hugging Face Inference Providers 中可用的模型名
```

远程模式分两种 RAG 档位：

- `RAG_MODE=lexical`：无需下载 Embedding，也不产生远程 Embedding 调用，适合零模型分享；本项目仍会展示知识库来源和可解释检索结果。
- `RAG_MODE=vector`：完整执行“切片 → 远程 Embedding → Chroma 持久化 → 向量检索”。需要远程服务商提供 Embedding endpoint、模型名和额度，在 `.env.remote` 填好 `RAG_EMBEDDING_MODEL`、`RAG_EMBEDDING_API_KEY` 后运行 `./scripts/index_remote.sh`。如果没有 Embedding 服务，不应把 lexical 模式宣传成向量 RAG。

远程聊天和远程 Embedding 是两个独立配置：某个免费聊天模型可用，不代表同一服务商的 Embedding 也免费或可用。官方参考：[OpenRouter Quickstart](https://openrouter.ai/docs/quickstart)、[OpenRouter 免费模型路由](https://openrouter.ai/docs/cookbook/get-started/free-models-router-playground)、[Hugging Face OpenAI-compatible endpoint](https://huggingface.co/changelog/inference-providers-openai-compatible)。

本地模型支持两种执行档位：

- `AGENT_EXECUTION_MODE=fast`：规则完成 Supervisor 分流，工具和 RAG 完成事实采集，风险/合规节点使用可审计的确定性规则，只调用一次模型生成最终报告，适合日常体验和同学演示。
- `AGENT_EXECUTION_MODE=full`：Supervisor、采集、风险、合规和报告节点都调用模型，适合面试时展示完整 Prompt 协作，但本地 8B 模型会明显变慢。

另外，Ollama 请求默认限制上下文和输出长度，并关闭 Qwen3 思考模式；这能显著减少首次演示的等待时间。需要更强质量时可以把 `LLM_MODEL` 改回 `qwen3:8b`，并切换到 `full`。

## Skill 系统

Skill 不是散落在 Prompt 里的说明，而是位于 `src/skills/**/SKILL.md` 的版本化 Markdown 规范。当前包含企业授信尽调、制度合规审查、财务指标分析、行业新闻检索和金融安全护栏五个 Skill；`SkillRegistry` 会读取 frontmatter、根据问题推荐 Skill，并将执行规则注入对应 Agent。

## MCP 工具边界

系统现在提供 `/mcp` JSON-RPC 工具端点，支持 `initialize`、`tools/list` 和 `tools/call`，工具仍受 `ToolGateway` 白名单和审计约束。可通过 `MCP_AUTH_TOKEN` 开启 Bearer Token 校验。它用于演示标准 MCP 工具调用边界；生产部署还应补充完整 Streamable HTTP 会话、限流和企业级认证。

## 完整向量 RAG

安装 RAG 依赖后，系统支持“文档切片 → Ollama 本地 Embedding → Chroma 持久化向量库 → 相似度检索 → 引用上下文”的完整流程：

```bash
./scripts/setup.sh       # 第一次：安装依赖、拉模型、建立向量库
./scripts/start.sh       # 以后：启动 Web 工作台
```

Windows PowerShell 使用：

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1
```

如果只想手动验证 RAG：

```bash
python -m src.rag.cli query "授信尽调需要哪些材料？"
```

`RAG_MODE=auto` 在向量库可用时会融合向量相似度和关键词重合度，向量服务不可用时明确降级为词法检索；如果要强制验证向量 RAG，将 `RAG_MODE=vector`，缺依赖或未建索引时直接报错，不会静默假装使用了向量库。也可以使用 Hugging Face 的 `BAAI/bge-small-zh-v1.5`，安装可选依赖 `pip install -e '.[rag-local]'`。

## 启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[documents,dev]'
cp .env.example .env
python run_agent.py
```

无模型也能先运行：保持 `.env` 中 `LLM_PROVIDER=demo`。验证：

```bash
pytest -q
uvicorn src.api.server:app --reload
```

打开 `http://127.0.0.1:8000/` 使用 Web 工作台。接口：`GET /health`（存活）、`GET /readiness`（模型/RAG 就绪状态）、`POST /chat` 和 `POST /mcp`。聊天请求体为 `{"message":"什么是反洗钱？"}`。

## 发给同学的交付方式

不要把 `.venv`、Ollama 模型文件、真实 API Key 或 `data/vector_db` 打包进 Git/压缩包。建议交付整个项目目录，让同学按需求选择下面一种路径：

### A. 无本地模型下载（推荐作品分享路径）

1. 安装 Python 3.10+。
2. macOS/Linux 执行 `./scripts/start_remote.sh`；Windows 执行 `.\scripts\start_remote.ps1`。
3. 在生成的 `.env.remote` 中填入同学自己的 API Key，再次运行脚本。
4. 浏览器打开 `http://127.0.0.1:8000/`。

### B. 完全离线演示

执行 `./scripts/start.sh --demo`，不需要模型、API Key 或外部服务，适合先看完整前端、LangGraph trace、Skill、RAG 来源和安全护栏。它是确定性演示，不是大模型推理。

### C. 本地开源模型

1. 安装 Python 3.10+ 和 Ollama。
2. macOS/Linux 执行 `./scripts/setup.sh`；Windows 执行 `.\scripts\setup.ps1`。
3. 以后直接执行启动脚本，浏览器打开 `http://127.0.0.1:8000/`。

本地路径首次需要下载约 2GB 模型和 Embedding；远程路径不下载大模型，但请求速度和可用性取决于服务商，且 Key 不应由作品作者共享。

## 重要边界

`data/knowledge_base` 当前放的是演示材料，不是正式制度库；CRM 也是本地演示数据。替换成真实系统时，应增加身份认证、权限控制、审计日志、数据脱敏和人工复核。系统不会给出授信批准/拒绝或个股买卖建议。
