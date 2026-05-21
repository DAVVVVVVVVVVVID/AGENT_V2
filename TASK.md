# AGENT_v2 任务列表

设计文档：`design_notes.md`
沙盒 API：`../SANDBOX/docs/api-spec.md`

---

## TASK001 — 项目结构重组

**内容：**
- 按照设计文档第十一节重组 `agent/` 目录：
  - 新建 `agent/memory/__init__.py`、`agent/memory/store.py`、`agent/memory/shadow.py`
  - 新建 `agent/retrieve.py`、`agent/plan.py`
  - 保留并更新 `agent/perceive.py`、`agent/think.py`、`agent/execute.py`、`agent/loop.py`、`agent/logger.py`、`agent/personality.py`、`agent/ui_server.py`
  - 新建 `memory/` 数据目录（运行时存储）：`memory/events/`、`memory/recognitions/`，并创建空的 `memory/Memory.md`、`memory/keywords.md`、`memory/purpose.md`
- 更新 `pyproject.toml` 中依赖（如有新增）

**验收标准：**
- `uv run python -c "from agent import memory"` 不报错
- `memory/` 数据目录及初始文件存在
- `memory/purpose.md` 有占位内容（如"在小镇中建立日常生活规律"）

---

## TASK002 — memory/store.py — 记忆文件读写

**内容：**
- `create_event(history, importance, keywords, summary)` → 生成 `memory/events/event_NNN.md`，写入标准 frontmatter + 三层正文（What/How/Why）
- `create_recognition(content, importance, keywords, summary)` → 生成 `memory/recognitions/recog_NNN.md`
- `update_memory_index(filepath, description, time, importance)` → 追加一行到 `memory/Memory.md`
- `update_keywords(keywords, filepath)` → 更新 `memory/keywords.md`，维护计数和反向文件列表
- `read_purpose()` → 返回 `memory/purpose.md` 全文
- `load_memory_index()` → 返回 `memory/Memory.md` 全文
- `load_files(filepaths)` → 读取并返回指定记忆文件正文列表

**验收标准：**
- 调用 `create_event` 后，对应文件存在，frontmatter 格式正确
- 调用 `update_keywords` 两次后，`keywords.md` 计数正确，反向索引含两个文件
- `Memory.md` 每次追加不覆盖原有内容

---

## TASK003 — memory/shadow.py — 影子 Agent

**内容：**
- `trigger_shadow_agent(history, llm, model)` — 异步函数，主 agent 调用 `finish()` 后触发
- 流程：调用 LLM 根据 history 生成 Event 记忆的三层内容（What/How/Why）、摘要、关键词、Importance 评分
- 调用 `store.create_event`、`store.update_memory_index`、`store.update_keywords` 写入结果
- 主 agent 不等待（`asyncio.create_task` 或线程）

**验收标准：**
- 传入 mock history（3轮），触发后 `memory/events/` 中出现新文件
- 主循环不阻塞（触发后立即返回，记忆文件异步写入）
- 生成的文件 frontmatter 字段完整（Description、Time、Keywords、Type、Importance）

---

## TASK004 — perceive.py — 感知模块

**内容：**
- 从 v1 迁移，接口不变
- 调用 `GET /agent/perceive`，返回 `arena_tree`、`vision_tiles`、`front_object`、`player_state`、`state_diff`

**验收标准：**
- 沙盒运行时，`perceive()` 返回结构与 v1 一致
- 沙盒未运行时，抛出明确异常而非静默失败

---

## TASK005 — retrieve.py — 两步 KW 检索

**内容：**
- `retrieve(task_or_plan, perceive_summary, llm, model)` → 返回 top 5 记忆文件正文列表
- **第一步**：小型 LLM 根据 task/感知摘要 + Memory.md 索引，选出 3–5 个关键词
- **第二步**：在 `keywords.md` 中查找关键词反向索引，合并候选文件列表，按 retrieval_score 排序，取 top 5
  - `retrieval_score = base_importance + time_decay_bonus + kw_match_score`
  - `time_decay_bonus = max(0, 3 - days_elapsed / 7)`
  - `kw_match_score = matched_kw_count * 0.5`
- 无记忆时返回空列表

**验收标准：**
- mock Memory.md（5条记忆）+ keywords.md，调用后返回正确排序的 top 5
- 空 Memory.md 时返回 `[]` 不报错
- LLM 选出的关键词不在 keywords.md 中时，安全跳过（不崩溃）

---

## TASK006 — think.py — 执行者 LLM

**内容：**
- 从 v1 迁移并重构
- `Think.think(plan, history, perceive_result, retrieved_memories)` → 返回 Action Sequence
- 利用 OpenAI API **multiple tool_calls**，单次响应返回多个 tool call
- 执行者 prompt（角色：逐步执行，关注具体行动）
- retrieved_memories 作为 attachment 注入 user message
- Memory.md 索引注入 system prompt

**验收标准：**
- LLM 返回至少 1 个 tool call（含 finish）
- 返回格式：`[{"name": str, "arguments": dict}, ...]`
- retrieved_memories 为空时正常运行

---

## TASK007 — plan.py — 规划者 LLM

**内容：**
- `Plan.generate(purpose, perceive_result, retrieved_memories, llm, model)` → 返回有序 Plan 列表
- 规划者 prompt（角色：长期规划，关注目标分解，思考粒度粗）
- 输出格式：JSON 列表，每个 Plan 为一个字符串描述
- 同样注入 Memory.md + retrieved_memories

**验收标准：**
- 传入 purpose + 感知结果，返回非空有序列表（≥1 个 Plan）
- 输出可解析为 Python list of str
- Plan 内容与 purpose 语义相关（人工判断）

---

## TASK008 — execute.py — Action Sequence 执行

**内容：**
- 从 v1 迁移并重构
- `execute_sequence(action_sequence, sandbox_client)` → 返回完整序列快照
- 按序执行每个 action，调用沙盒 API
- 成功：记录结果（新坐标、阅读内容等）
- 失败：记录失败原因，立即停止，后续标记"未执行"
- 返回格式：
  ```python
  [
      {"name": "move_direction", "arguments": {...}, "status": "success", "result": {...}},
      {"name": "use_object",     "arguments": {},    "status": "failed",  "reason": "no_object_in_front"},
      {"name": "observe_object", "arguments": {},    "status": "pending"},
  ]
  ```

**验收标准：**
- 第 2 个 action 失败时，第 3 个状态为 `"pending"`
- 全部成功时，所有状态为 `"success"`
- finish() 在序列中时，正确识别并终止内层循环

---

## TASK009 — loop.py — 双层循环

**内容：**
- **外层循环** `run_outer(config)`：
  - 读取 purpose → Perceive → Retrieve → Plan.generate → 得到 Plan Batch（有序列表）
  - 进入内层循环逐个执行 Plan
  - Plan Batch 全部完成后重新外层循环
- **内层循环** `run_inner(plan, ...)`：
  - Perceive → Retrieve → Think → execute_sequence
  - 序列中出现 finish()：触发 shadow agent，结束本 Plan
  - 传给下一轮的 history 包含完整序列快照
- pause/resume 支持（继承 v1 机制）

**验收标准：**
- 沙盒运行时，agent 自动生成 Plan Batch 并逐个执行，不需要手动输入任务
- finish() 后，shadow agent 异步写入 Event 记忆
- Plan Batch 耗尽后，自动触发下一次外层循环（重新规划）
- pause 后循环停止在当前轮结束处，resume 后继续

---

## TASK010 — ui_server.py — 自驱动 UI

**内容：**
- 移除手动任务输入框（改为自动运行）
- 新增启动/停止按钮（控制整个双层循环）
- 显示当前状态：外层循环（规划中）/ 内层循环（执行 Plan X/N）
- 保留 v1 的 pause/resume、chat panel、logging 开关
- 实时展示当前 Plan Batch 列表及各 Plan 完成状态

**验收标准：**
- 点击启动后，agent 自动开始运行，UI 实时更新状态
- Plan Batch 列表可见，当前执行的 Plan 有高亮标记
- pause/resume/chat 功能与 v1 一致
- 点击停止后，循环在当前轮结束时退出
