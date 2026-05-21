# AGENT v2

在 AGENT v1 的 ReAct 循环基础上演进的**自驱动 Agent**，无需用户逐次输入任务。Agent 根据自身的 Purpose（最高目标）自主生成 Plan、分批执行、积累记忆，持续在 BASIC_SANDBOX 2D 虚拟世界中生活。

> **版本说明：** 当前版本为 **Agent v2.0.0**，对应可稳定运行的沙盒版本为 **Sandbox v1.0.0**。

---

## 与 v1 的核心区别

| 特性 | AGENT v1 | AGENT v2 |
|------|----------|----------|
| 驱动方式 | 用户每次输入任务 | 自驱动（Purpose → Plan → Action） |
| 记忆系统 | 无 | Event / Recognition + 检索 |
| 行动输出 | 单个 tool call | Action Sequence（多步原子行动） |
| 规划层 | 无 | 专用 Planner，批量生成 Plan |
| 感知后处理 | 直接进入 Think | Retrieve 阶段补充相关记忆 |

---

## 架构概览

```
Purpose（最高目标）
     │
     ▼
┌──────────────────────────────────────────────────┐
│                   外层循环                        │
│  Perceive → Retrieve → Planner → Plan Batch       │
│                              │                    │
│         ┌────────────────────┘                    │
│         │  对每个 Plan 执行内层循环               │
│         ▼                                         │
│  ┌─────────────────────────────────────────┐      │
│  │              内层循环（ReAct）           │      │
│  │  Perceive → Retrieve → Think            │      │
│  │      ▲          │ Action Sequence       │      │
│  │      │          ▼                       │      │
│  │      └──── Execute ──► finish()?        │      │
│  │                             │           │      │
│  │                    Shadow Agent ──► Event 记忆  │
│  └─────────────────────────────────────────┘      │
└──────────────────────────────────────────────────┘
```

| 模块 | 职责 |
|------|------|
| **Perceive** | 获取当前区域语义树、视野 tile、正前方物体 |
| **Retrieve** | 两步关键词检索，从记忆库中取出最相关的 5 条记忆 |
| **Planner** | 根据 Purpose + 感知 + 记忆，一次生成多个 Plan |
| **Think** | 输出 Action Sequence（多个原子行动） |
| **Execute** | 逐步执行行动序列，记录完整快照 |
| **Shadow Agent** | finish() 触发后台线程，LLM 生成 Event 记忆文件 |

---

## 记忆系统

```
memory/
├── purpose.md          # 最高目标（持久，可在 UI 中编辑）
├── Memory.md           # 全量记忆索引（自动追加，注入 system prompt）
├── keywords.md         # 关键词反向索引（用于检索）
├── events/             # Event 记忆（Shadow Agent 客观记录行动经过）
│   └── event_NNN.md
└── recognitions/       # Recognition 记忆（主观感想，待实现）
    └── recog_NNN.md
```

**检索流程：**
1. Think 调用前，LLM 从当前 Plan 和感知摘要中抽取关键词
2. 用关键词查 `keywords.md` 反向索引，得到候选文件列表
3. 按 `base_importance + 时效性加成 + 关键词匹配数` 打分，取 Top 5 注入 prompt

**Action Sequence 快照格式（每步）：**
```json
{
  "name": "move_to_tile",
  "arguments": {"x": 3, "y": 5},
  "status": "success | failed | pending",
  "result": { ... }
}
```

---

## 环境要求

| 依赖 | 版本要求 | 说明 |
|------|---------|------|
| Python | ≥ 3.11 | 建议使用 [uv](https://github.com/astral-sh/uv) 管理 |
| [BASIC_SANDBOX](../SANDBOX) | v1.0.0 | 后端沙盒，默认监听 `http://localhost:8000` |
| [Ollama](https://ollama.com) | ≥ 0.24.0 | 本地 LLM 推理，默认端口 `11435` |
| qwen3:32b | Q4_K_M | 推荐量化版本（约 20 GB） |

### 启动 Ollama（GPU Docker 方式）

```bash
sudo docker run -d \
  --name ollama-gpu \
  --restart unless-stopped \
  --gpus all \
  -p 11435:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama:0.24.0
```

---

## 安装

```bash
cd AGENT_v2
uv sync
```

---

## 配置

编辑 `agent/config.py`：

```python
AGENT_CONFIG = {
    "name":       "小明",          # Agent 角色名
    "entity_id":  "player_01",    # 沙盒中对应的实体 ID

    # OCEAN 人格模型（0–100）
    "ocean": {"O": 70, "C": 60, "E": 50, "A": 75, "N": 30},

    "lifestyle":    [...],        # 生活习惯，注入 system prompt
    "common_sense": [...],        # 坐标系与行动规则常识

    "vision_size":  3,                           # 视野半径（tile）
    "llm_base_url": "http://localhost:11435/v1", # Ollama API 地址
    "model":        "qwen3:32b",                 # 使用的模型
}
```

**Purpose 配置：** 编辑 `memory/purpose.md`，或在 UI 控制面板的记忆查看器中修改。

---

## 运行

```bash
uv run python -m agent.ui_server
```

浏览器访问 `http://localhost:8001`，点击 **启动** 即可。

### 控制面板功能

| 区域 | 功能 |
|------|------|
| Agent 参数面板 | 查看角色配置、OCEAN 值、Purpose |
| Player 状态面板 | 实时位置、HP、Energy、当前 Buff |
| Plan 状态面板 | Plan Batch 进度（✓ 已完成 / ▶ 进行中 / ○ 待执行） |
| Loop 输出面板 | 每轮感知、思考、行动序列、执行结果的实时日志 |
| 对话框 | 暂停时与 Agent 对话，可选择"注入记忆" |
| 记忆查看器 | 独立页面，查看 Purpose / Memory Index / Keywords / Events / Recognitions |
| 清除记忆 | 可选择性清除 Events、Recognitions、辅助索引或 Purpose |
| 强制重置 | Player 有阻塞性 Buff 时出现，强制离开对象并清除所有 Buff |

---

## 项目结构

```
AGENT_v2/
├── agent/
│   ├── config.py          # Agent 参数配置
│   ├── perceive.py        # 感知模块
│   ├── retrieve.py        # 两步关键词检索
│   ├── plan.py            # Plan Batch 生成（专用 Planner）
│   ├── think.py           # Action Sequence 生成
│   ├── execute.py         # 行动序列执行与快照
│   ├── loop.py            # 两层自驱动主循环
│   ├── memory/
│   │   ├── store.py       # 记忆文件 CRUD、索引维护
│   │   └── shadow.py      # Shadow Agent（后台 Event 记录）
│   ├── sandbox_client.py  # 沙盒 HTTP 客户端封装
│   ├── personality.py     # OCEAN → 文字描述转换
│   ├── logger.py          # 运行日志写入
│   └── ui_server.py       # FastAPI Web 控制面板
├── memory/
│   ├── purpose.md         # 最高目标（纳入版本控制）
│   ├── events/            # Event 记忆（运行时生成，已 gitignore）
│   └── recognitions/      # Recognition 记忆（运行时生成，已 gitignore）
├── pyproject.toml
└── README.md
```

---

## 沙盒依赖

Agent 通过 HTTP 调用 [BASIC_SANDBOX](../SANDBOX) 后端，在 v1 基础上额外使用：

| 接口 | 用途 |
|------|------|
| `GET /agent/perceive` | 感知信息 |
| `GET /agent/arena-tiles` | 指定 arena 内 tile 坐标 |
| `GET /agent/object-position` | 指定 object 锚点坐标 |
| `POST /action` | 执行行动（move / use / leave 等） |
| `GET /player` | 玩家状态（含 Buff 列表） |
| `GET /admin/player/buffs` | 查看当前 Buff（调试用） |
| `POST /admin/player/force-reset` | 强制清除 Buff / 离开对象（调试用） |

完整接口规范见 [`../SANDBOX/docs/api-spec.md`](../SANDBOX/docs/api-spec.md)。
