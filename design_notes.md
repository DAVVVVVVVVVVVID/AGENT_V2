# AGENT_v2 设计笔记

## 记忆系统设计

### 一、文件结构

```
memory/
├── purpose.md          # 最高层目标（特殊文件，只能通过 Reflection 修改）
├── Memory.md           # 全量索引，加载到 system prompt
├── keywords.md         # 关键词表（频次 + 反向文件索引）
├── events/             # 事件记忆（客观记录）
│   ├── event_001.md
│   └── ...
└── recognitions/       # 认知记忆（主观记录）
    ├── recog_001.md
    └── ...
```

---

### 二、记忆文件格式（通用 header）

每个记忆文件（event / recognition）均以如下 frontmatter 开头：

```markdown
---
Description: <一句话摘要>
Time: <ISO 8601，记忆创建时刻>
Keywords: [kw1, kw2, kw3]
Type: event | recognition
Importance: <0–10，LLM 在创建时评分>
---

<正文内容>
```

**Importance 评分（0–10）：** 由生成该记忆的 LLM 在创建时一次性打分，基准如下：
- 0–3：日常琐事，低重复价值
- 4–6：有参考价值的经历
- 7–9：重要事件或关键认知
- 10：极少数，改变目标/世界观的事件

---

### 三、Memory.md（全量索引）

格式：每条记忆一行，包含文件路径、Description、Time、Importance。

```
- [event_001](events/event_001.md) — <Description> | 2026-05-01T10:00 | imp=8
- [recog_001](recognitions/recog_001.md) — <Description> | 2026-05-01T11:00 | imp=6
```

**作用：** 在每次 Retrieve 阶段之前，Memory.md 完整加载进 system prompt，让检索 agent 知道所有记忆的摘要，从而做 KW 选择。

---

### 四、keywords.md（关键词反向索引）

格式：每行一个关键词，含出现频次与关联文件列表。

```
睡觉: 3, [events/event_001.md, events/event_005.md, recognitions/recog_002.md]
厨房: 2, [events/event_002.md, recognitions/recog_001.md]
疲劳: 1, [recognitions/recog_003.md]
```

**作用：** Retrieve 阶段第二步，检索 agent 根据选出的关键词，从这里找到关联文件。

---

### 五、记忆类型详解

#### 5.1 Event 记忆（事件记忆）

- **定义：** 客观发生的事，记录 what/how/why
- **生成者：** 影子 Agent（Shadow Agent），异步、后台运行
- **触发时机：** 主 agent 调用 `finish()` 时，当前 Plan 完成
- **内容三层结构：**
  1. **What（发生了什么）：** Plan 的目标是什么，实际完成了什么
  2. **How（怎么做到的）：** 关键步骤、用了哪些 tool、遇到什么障碍
  3. **Why（为什么这样做）：** 背后的 Purpose / 上下文原因

#### 5.2 Recognition 记忆（认知记忆）

- **定义：** 主观感受、价值判断、情感状态、对事物的看法
- **生成者：** 主 agent 自身，通过 tool call 触发
- **触发时机：** agent 在 Think 阶段判断需要记录某种认知时主动调用
- **举例：** "我发现厨房的冰箱总是空的，这让我感到不安" / "今天的任务完成得很顺利，我对自己的效率感到满意"

---

### 六、检索机制（两步检索）

Retrieve 阶段在 Perceive 之后、Think 之前，由一个独立的小型 LLM agent 执行。

#### 第一步：KW 选择

- 输入：当前 task / 当前感知摘要 + **完整 Memory.md 索引**
- 输出：3–5 个关键词（从 keywords.md 已有词中选，或新词）
- 模型：轻量模型即可（如 qwen3:8b）

#### 第二步：文件命中 + Importance 排序

- 根据第一步选出的 KW，在 keywords.md 中查找反向索引，合并关联文件列表（去重）
- 对每个候选文件计算**检索时 Importance 分**：

```
retrieval_score = base_importance
                + time_decay_bonus
                + kw_match_score

time_decay_bonus = max(0, 3 - days_elapsed / 7)   # 最近 3 周内有加分
kw_match_score   = matched_kw_count * 0.5          # 每命中一个 KW 加 0.5 分
```

- 取 top 5 文件，加载正文内容，注入 Think 阶段 prompt

---

### 七、purpose.md（最高层目标）

- **特殊文件：** 不走普通记忆流程，独立存在
- **内容：** agent 的最高层、长期目标（如"在小镇中建立日常生活规律"）
- **修改限制：** 只能通过 **Reflection 机制**（未来实现）修改，主 agent 无法直接改写
- **加载方式：** 每次循环开始时读入，作为 Plan 生成的最高约束

---

### 八、Purpose → Plan → Action 三层循环（自驱动）

替代 AGENT_v1 的手动任务输入，agent 自主产生任务：

```
Purpose（最高层目标，长期稳定）
  └─ Plan Batch（一批 Plan，有序列表，一次性生成）
       └─ Plan（中期目标，逐个执行，全部完成后才重新生成下一批）
            └─ Action Sequence（原子行动序列，Think 每次输出多步）
```

#### 8.1 整体两层循环结构

```
【外层循环 — 规划者】
  Perceive → Retrieve → Plan Batch 生成（有序列表）
      ↓
  【内层循环 — 执行者，逐个 Plan】
    Perceive → Retrieve → Think（Action Sequence）→ Execute → finish()
    取下一个 Plan，重复内层循环
      ↓
  内层全部完成 → 回到外层循环，重新 Perceive → Retrieve → 生成新一批 Plan
```

#### 8.2 外层循环（规划者）

- **Perceive：** 与内层相同，调用同一个 `/agent/perceive` 接口
- **Retrieve：** 与内层相同机制——Memory.md 在 system prompt，KW 检索 top 5 记忆作为 attachment
- **Plan Batch 生成：**
  - 输入：Purpose（`purpose.md`）+ 当前感知 + 检索记忆
  - 输出：有序的 Plan 列表（LLM 决定执行顺序）
  - 使用**规划者 prompt**（角色定位为长期规划，思考粒度粗，关注目标分解）
- **触发时机：** 启动时 / 当前批次全部 `finish()` 后

#### 8.3 内层循环（执行者）

- 从 Plan Batch 中按序取当前 Plan 作为任务目标
- 使用**执行者 prompt**（角色定位为逐步执行，思考粒度细，关注具体行动）
- 每次 `finish()` 后触发影子 Agent 生成 Event 记忆，然后取下一个 Plan
- Perceive / Retrieve 机制与外层相同

#### 8.4 LLM 与 Prompt 说明

| | 外层（规划者） | 内层（执行者） |
|---|---|---|
| LLM 模型 | 相同模型 | 相同模型 |
| Prompt 角色 | 长期规划者，负责目标分解 | 具体执行者，负责步骤决策 |
| 输出格式 | 有序 Plan 列表 | Action Sequence（tool calls）|
| Retrieve 机制 | 相同 | 相同 |

---

### 九、Action Sequence 细节

#### 9.1 输出格式

Think 利用 OpenAI API 原生支持的 **multiple tool_calls**，在单次响应中返回多个 tool call，构成本轮的行动序列。

#### 9.2 执行与结果记录

Execute 按序逐个执行 tool_calls：
- **成功：** 记录执行结果（如位移后的新坐标、阅读到的对象描述）
- **失败：** 记录失败原因，立即停止，后续未执行的行动标记为"未执行"

无论成功与否，**完整序列快照**都提交给下一轮循环作为 observation，格式示例：

```
行动1: move_direction(up, 3)  → 成功，移动到 (3, 2)
行动2: turn(right)            → 成功，朝向 right
行动3: use_object()           → 失败，no_object_in_front
行动4: observe_object()       → 未执行
```

#### 9.3 下一轮循环入口

执行序列结束后（全部成功或中途失败），无论结果如何，都重新走 **Perceive → Retrieve → Think** 循环，携带上述完整序列快照作为历史 observation。

---

### 十、影子 Agent（Shadow Agent）

- 主 agent 调用 `finish()` 后异步触发
- 读取当前 Plan 完整历史（history），生成 Event 记忆文件
- 写入 events/ 目录，更新 Memory.md 和 keywords.md
- 主 agent 不等待影子 agent，继续生成下一个 Plan

---

### 十、暂时搁置的机制

- **Reflection（反思）：** 唯一能修改 `purpose.md` 的机制，未来实现
  - 触发条件：累计若干次 Plan 完成后，或 Importance 极高事件出现
  - 流程：独立 LLM 对近期记忆做高阶归纳，判断是否需要调整 Purpose

---

### 十一、代码结构

```
agent/
├── memory/             # 记忆系统（独立子包）
│   ├── __init__.py
│   ├── store.py        # Event/Recognition 文件读写、Memory.md、keywords.md 维护
│   └── shadow.py       # 影子 Agent（异步，finish() 后触发）
│
├── loop.py             # 外层（规划者）+ 内层（执行者）两个循环
├── perceive.py         # 感知，与 v1 基本不变
├── retrieve.py         # 两步 KW 检索 agent
├── plan.py             # 规划者 LLM 调用，输出有序 Plan Batch
├── think.py            # 执行者 LLM 调用，输出 Action Sequence（multiple tool_calls）
├── execute.py          # 按序执行 Action Sequence，记录每步结果
│
├── personality.py      # 不变
├── logger.py           # 更新以支持 v2 日志格式
└── ui_server.py        # 更新以支持自驱动模式
```

**模块职责说明：**
- `memory/store.py`：所有记忆文件的 CRUD，包括 Memory.md 索引和 keywords.md 反向索引的维护
- `memory/shadow.py`：异步影子 Agent，`finish()` 后触发，读取历史生成 Event 记忆
- `retrieve.py`：独立小型 LLM agent，外层/内层循环共用，执行两步 KW 检索
- `plan.py`：规划者角色，输出有序 Plan 列表，prompt 与 think.py 完全不同
- `think.py`：执行者角色，输出 multiple tool_calls（Action Sequence）
- `execute.py`：按序执行，遇失败立即停止，返回完整序列快照（含成功结果/失败原因/未执行标记）
- `loop.py`：外层规划循环 + 内层执行循环，两层放一起以清晰体现嵌套关系

---

### 十二、与 AGENT_v1 的主要差异

| 维度 | AGENT_v1 | AGENT_v2 |
|------|----------|----------|
| 任务来源 | 用户手动输入 | 自驱动（Purpose→Plan） |
| 循环结构 | Perceive→Think→Execute | Perceive→Retrieve→Think→Execute |
| Think 输出 | 单个 tool call | 原子行动序列 |
| 记忆系统 | 无 | Event + Recognition + Purpose |
| 检索机制 | 无 | 两步 KW 检索 + Importance 排序 |
| 影子 Agent | 无 | 有（异步生成 Event 记忆） |
