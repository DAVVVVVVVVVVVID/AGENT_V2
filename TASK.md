# AGENT_v1 任务清单

> 执行顺序：TASK001 → TASK011，存在依赖关系，不可乱序。
> 每个 TASK 完成后更新状态：`[ ]` → `[x]`

---

## TASK001 · 项目初始化

**状态**：`[x]`

**目标**：建立 AGENT_v1 的 uv 项目结构和目录。

**内容**：
- 初始化 uv 项目（`pyproject.toml`），Python 版本 ≥ 3.11
- 添加依赖：`openai`（LLM 调用）、`httpx`（沙盒 API 调用）
- 创建目录结构：
  ```
  AGENT_v1/
  ├── agent/
  │   ├── __init__.py
  │   ├── main.py           # 入口
  │   ├── loop.py           # 循环主控
  │   ├── perceive.py       # Perceive 模块
  │   ├── think.py          # Think 模块
  │   ├── execute.py        # Execute 模块
  │   ├── personality.py    # OCEAN 描述生成
  │   ├── sandbox_client.py # 沙盒 API 客户端
  │   └── config.py         # Agent 配置（profile、视野半径等）
  ```

**验收标准**：
- `uv sync` 无报错
- `uv run python -c "import agent"` 无报错

---

## TASK002 · OCEAN 性格描述生成模块

**状态**：`[x]`

**目标**：将 OCEAN 五维评分转换为自然语言描述。

**内容**：
- 文件：`agent/personality.py`
- 输入：5 个维度各 0–100 的浮点分数 `{O, C, E, A, N}`
- 输出：一段描述性文字，根据分数高低动态生成（不同区间对应不同描述词）
- 函数签名：`def ocean_to_description(o, c, e, a, n) -> str`

**验收标准**：
- 调用 `ocean_to_description(80, 40, 60, 70, 30)` 返回一段合理的中文描述
- 分别将某一维度调高/调低，输出中对应描述词发生变化

---

## TASK003 · 沙盒 API 客户端

**状态**：`[x]`

**目标**：封装所有现有沙盒 HTTP 接口，供各模块调用。

**内容**：
- 文件：`agent/sandbox_client.py`
- 封装以下接口（base_url 可配置，默认 `http://localhost:8000`）：
  - `get_world() -> dict`
  - `get_player() -> dict`
  - `get_events() -> list`
  - `get_history() -> list`
  - `post_action(entity_id, action_type, payload) -> dict`

**验收标准**：
- 沙盒后端运行时，调用每个方法均能返回正确数据
- `post_action("player_01", "move", {"direction": "up"})` 返回包含 `success` 字段的响应

---

## TASK004 · 沙盒改造：多步移动 API

**状态**：`[x]`

**目标**：新增 `move_n` action type，支持一次向某方向移动 N 格，不修改现有 `move`。

**内容**：
- 修改文件：`SANDBOX/back_end/routers/actions.py`，新增 `handle_move_n` handler 并注册
- payload：`{"direction": "up"|"down"|"left"|"right", "steps": N}`
- 逐格执行，每格独立校验 walkable，遇阻立即停止并返回实际到达位置和实际步数
- 同步更新 `SANDBOX/docs/api-spec.md`

**验收标准**：
- `POST /action {"type": "move_n", "payload": {"direction": "up", "steps": 3}}` 成功时 player 向上移动最多 3 格
- 若中途有不可行走格，停在最后一个可行走格，`result` 中包含 `steps_taken` 和最终 `position`
- 原有 `move` action 行为完全不变

---

## TASK005 · 沙盒改造：Perceive 专用端点

**状态**：`[x]`

**目标**：新增 `GET /agent/perceive` 接口，一次返回 agent 感知所需的全部信息。

**内容**：
- 新增文件：`SANDBOX/back_end/routers/agent.py`
- 新增路由：`GET /agent/perceive?entity_id=player_01&vision_radius=3`
- 返回内容：
  1. **arena 语义树**：当前 arena 内的 world / sector / arena 名称 + object 列表（名称、是否可交互）；无坐标
  2. **视野 tile 列表**：以当前位置为中心，radius 范围内每个 tile 的坐标、类型、所属 arena、object（若有）
  3. **正前方格子**：正前方一格是否有 object，若有则返回 object id 和名称
- 同步更新 `SANDBOX/docs/api-spec.md`

**验收标准**：
- 沙盒运行时调用接口，返回包含上述三部分的 JSON
- arena 语义树中无任何坐标字段
- 视野列表格数 ≤ (2×radius+1)²（边界 tile 超出地图则不返回）
- 正前方有 object 时返回 object 信息，无 object 时返回 null

---

## TASK006 · 沙盒改造：区域导航 & 坐标查询

**状态**：`[x]`

**目标**：新增 agent Think 阶段所需的两类信息查询接口，以及区域随机导航 action。

**内容**：

查询接口（新增到 `SANDBOX/back_end/routers/agent.py`）：
- `GET /agent/arena-tiles?arena_id=xxx` → 返回该 arena 所有 tile 坐标列表
- `GET /agent/object-position?object_id=xxx` → 返回该 object 的坐标

新增 action type（修改 `SANDBOX/back_end/routers/actions.py`）：
- type: `move_to_area`
- payload: `{"area_type": "arena"|"sector"|"world", "area_id": "xxx"}`
- 行为：在目标区域内随机选取一个可行走坐标，调用 targetTile 移动逻辑移动过去
- 同步更新 `SANDBOX/docs/api-spec.md`

**验收标准**：
- `GET /agent/arena-tiles?arena_id=xxx` 返回坐标列表，所有坐标确实属于该 arena
- `GET /agent/object-position?object_id=xxx` 返回正确坐标
- `POST /action {"type": "move_to_area", "payload": {"area_type": "arena", "area_id": "xxx"}}` 执行后 player 出现在目标 arena 内某可行走位置

---

## TASK007 · Perceive 模块

**状态**：`[x]`

**目标**：实现 agent 的感知模块，输出结构化感知结果。

**内容**：
- 文件：`agent/perceive.py`
- 调用 `GET /agent/perceive` 获取环境信息
- 调用 `GET /player` 获取完整玩家状态
- 与上一次状态快照做 diff，输出变化字段（监控字段：`position`、`facing`、`state`、`stateLabel`、`hp`、`energy`、`buffs`、`tags`、`usingObjectId`）
- 返回结构：
  ```python
  {
    "arena_tree":    {...},  # 语义树
    "vision_tiles":  [...],  # 视野 tile
    "front_object":  {...},  # 正前方 object 或 null
    "player_state":  {...},  # 完整玩家状态
    "state_diff":    {...},  # 变化的字段
  }
  ```

**验收标准**：
- 首次调用：`state_diff` 包含所有监控字段（无上次快照，视为全部变化）
- 连续两次调用且玩家未移动：`state_diff` 为空
- player 移动后调用：`state_diff` 中出现 `position` 字段

---

## TASK008 · Think 模块

**状态**：`[x]`

**目标**：实现 agent 的思考模块，调用 LLM 输出结构化 tool call。

**内容**：
- 文件：`agent/think.py`
- 构建 prompt，包含：
  - agent 性格描述（调用 `ocean_to_description`）
  - agent 生活方式列表
  - 当前任务目标
  - 历史记忆（最近 10 轮 Thought + Action + Observation）
  - Perceive 输出（arena 树 + 视野 + 正前方 object + 完整玩家状态）
- 将所有可用行为定义为 tools（含 finish），tool 列表：
  `get_arena_tiles`, `get_object_position`, `move_to_tile`, `move_direction`, `turn`, `use_object`, `observe_object`, `leave_object`, `move_to_area`, `finish`
- 调用 LLM（endpoint: `http://localhost:11435/v1`，model: `qwen3:32b`）
- 返回：`{"thought": "...", "tool_call": {"name": "...", "arguments": {...}}}`

**验收标准**：
- 给定简单感知输入，Think 返回合法 tool call（name 在可用列表内，arguments 结构正确）
- `thought` 字段非空
- 给定"任务已完成"的场景描述，LLM 选择 `finish` tool

---

## TASK009 · Execute 模块

**状态**：`[x]`

**目标**：将 Think 输出的 tool call 转为沙盒 API 调用，并生成 Observation。

**内容**：
- 文件：`agent/execute.py`
- 接收 tool call，映射到对应的沙盒 API 调用（通过 `sandbox_client`）
- 每个 tool 对应固定 Observation 模板（成功/失败均有对应中文描述）
- `finish` tool 不调用沙盒，直接返回总结
- 返回：`{"observation": "...", "is_finish": bool, "finish_reply": "..."}`

**验收标准**：
- `move_to_tile` 成功：observation 包含目标坐标和最终位置
- `move_to_tile` 失败（不可行走）：observation 包含失败原因
- `finish` tool：`is_finish=True`，`finish_reply` 为 LLM 生成的总结文字

---

## TASK010 · 循环主控 & 入口

**状态**：`[x]`

**目标**：实现完整的 ReAct 循环及用户启动入口。

**内容**：
- 文件：`agent/loop.py`（循环主控）、`agent/main.py`（入口）
- 循环逻辑：Perceive → Think → Execute → 存历史 → 检测 finish → 继续或退出
- 历史滚动窗口：最多保留 10 轮，超出自动丢弃最旧一条
- 入口参数：
  - `--task`：任务目标字符串
  - `--entity_id`：默认 `player_01`
  - agent profile 从 `config.py` 读取

**验收标准**：
- `uv run python -m agent.main --task "去沙发上休息"` 能启动循环
- 每轮终端打印：轮次、Thought、Action、Observation
- finish 后正常退出并打印最终总结
- 历史超过 10 轮后，最旧条目自动丢弃

---

## TASK011 · 端到端集成测试

**状态**：`[x]`

**前提**：沙盒后端已启动，Ollama GPU 容器运行中（端口 11435）。

**测试场景**：
1. 给定简单任务（如"找到沙发并使用它"），agent 能在若干轮内完成并触发 finish
2. 给定无法完成的任务，观察 agent 是否在多轮后选择 finish 并说明原因

**验收标准**：
- 场景 1：agent 实际移动到沙发位置，调用 use_object，最终输出完成总结
- 每轮日志清晰展示 Thought / Action / Observation
- 无未捕获异常，沙盒状态与 agent 行为一致
