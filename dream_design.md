# Dream 机制设计文档

> 本文档记录 AGENT_v2 Dream 机制的完整设计决策，作为后续开发的唯一依照。
> 所有实现必须以本文档为准，如有调整须先更新本文档。

---

## 一、概念定义

**Dream** 是 agent 的认知整理状态：在积累了足够的行为和记忆之后，进入 dream 状态，完成记忆整合、高阶认知提炼和 Purpose 更新，从而对世界有更清晰的认知，形成更稳定的行为特征。

Dream 期间 agent **不执行任何行动**（offline），等 dream 结束后继续正常 loop。

---

## 二、触发机制

### 2.1 三种触发条件

| 参数 | 类型 | 说明 | -1 或 null 表示 |
|---|---|---|---|
| `memory_count` | int | 上次 dream 后新增记忆数 ≥ 阈值 | 禁用此条件 |
| `time_minutes` | int | 距上次 dream 经过分钟数 ≥ 阈值 | 禁用此条件 |
| `time_of_day` | str\|null | 当前时刻进入指定时段，如 `"23:00"` | 禁用此条件 |

触发逻辑：**任意一个启用的条件满足即触发（OR）**。

### 2.2 触发时机

Dream 标志被设置后**不立即打断**当前执行。必须等当前 Plan 完成（`plan_finish` 事件之后）才进入 dream。实现方式类比 `_interrupt_flag`。

### 2.3 配置位置

profile yaml 中新增：

```yaml
dream:
  memory_count: 20    # -1 禁用
  time_minutes: 30    # -1 禁用
  time_of_day: null   # 如 "23:00"，null 禁用
```

---

## 三、记忆系统扩展

### 3.1 新增记忆类型：consolidated

在现有 `event` / `recognition` 基础上新增第三种类型。

**触发条件**：整合记忆由 Dream 的整合阶段创建，不会在正常 loop 中产生。

**文件位置**：`memory/consolidated/consolidated_001.md`（新建目录）

**文件格式**：

```markdown
---
Description: 关于电视的所有已知认知
Time: 2026-05-30T23:00:00+00:00
Importance: 18
Keywords: [电视, 客厅, 娱乐, buff]
Type: consolidated
Sources: [events/event_003.md, events/event_007.md, recognitions/recog_002.md]
---

## 内容

（由 LLM 综合所有来源记忆生成的完整认知描述）
```

**Importance**：所有来源记忆 importance 的**总和**。

**Sources**：来源记忆的相对路径列表（相对于 `memory/` 目录），同一条记忆可以出现在多个整合记忆的 Sources 中。

### 3.2 整合记忆的索引管理

- **原始来源记忆**：从 `Memory.md` 和 `keywords.md` 中**移除**（文件本身保留在磁盘，不删除）
- **整合记忆**：以标准格式新增进 `Memory.md` 和 `keywords.md`

Memory.md 条目格式（整合记忆与其他类型一致）：

```
- [consolidated_001](consolidated/consolidated_001.md) — 关于电视的所有已知认知 | 2026-05-30T23:00:00+00:00 | imp=18
```

### 3.3 整合记忆的更新（再次整合）

当新一轮 Dream 发现新记忆与已有整合记忆同属一个主题时：

- **有一个已有整合记忆**：追加新记忆到 Sources，重新生成 content，更新 Importance
- **有多个已有整合记忆**：由 LLM 判断是否主题重叠足够大，决定合并（Sources 合并，content 重写）或各自独立更新
- **无已有整合记忆**：新建一个整合记忆

### 3.4 高阶 Recognition

Dream 的提炼阶段生成的更高层级认知，本质仍是认知，**类型保持 `recognition`**。

与普通 recognition 的区别：

| 属性 | 普通 recognition | 高阶 recognition |
|---|---|---|
| 产生时机 | Think 阶段，agent 主动调用 | Dream 提炼阶段自动生成 |
| 来源 | 当前轮次的直接经历 | 基于多条记忆的模式推论 |
| 有 Sources 字段 | 无 | 有（列出支撑证据记忆） |
| 来源记忆隐去 | 不适用 | **不隐去**（保留在 Memory.md） |

高阶 recognition frontmatter 示例：

```markdown
---
Description: 使用 buff 类 object 后移动效率更高
Time: ...
Importance: 10
Keywords: [buff, 移动, 策略]
Type: recognition
Sources: [events/event_002.md, consolidated/consolidated_003.md]
---
```

---

## 四、Dream 执行流程

### 顺序（必须按序执行）

```
Step 1  阅读
Step 2  整合
Step 3  提炼（高阶 recognition）
Step 4  更新 Purpose
```

### Step 1：阅读

- 读取当前 `Memory.md` 中所有条目的**完整文件内容**（events、recognitions、consolidated）
- 额外读取上次 dream 之后新增的记忆（通过 `last_dream_time` 过滤）
- 上述内容作为 dream LLM 的输入上下文

### Step 2：整合

LLM 接收所有记忆，执行：

1. 聚类：将相关记忆分组
2. 对每组：判断是否有已有整合记忆 → 新建或更新
3. 将被整合的原始记忆从 `Memory.md` 和 `keywords.md` 中移除
4. 将新建/更新的整合记忆写入文件并加入 `Memory.md` 和 `keywords.md`
5. 记录 `last_dream_time`

### Step 3：提炼

LLM 基于整合后的全局视角（所有整合记忆 + 新产生的认知）：

1. 识别跨记忆的规律和模式
2. 生成若干条高阶 recognition（可以为 0 条，不强制）
3. 写入文件，加入 `Memory.md` 和 `keywords.md`
4. 来源记忆**不从索引中移除**

### Step 4：更新 Purpose

LLM 基于整合后的全局视角判断 Purpose 是否需要变化，输出结构化结果：

```json
{
  "action": "keep" | "modify" | "replace",
  "items": ["条目1", "条目2", ...]
}
```

- `keep`：不修改 purpose.md
- `modify`：对部分条目进行增加、修改或删除
- `replace`：完全重写所有条目

### 日志输出

每步完成后向 `_msg_queue` 发送事件：

```python
{"type": "dream_start"}
{"type": "dream_step", "step": "consolidate"|"reflect"|"purpose", "summary": "..."}
{"type": "dream_end", "purpose_action": "keep"|"modify"|"replace"}
```

---

## 五、Purpose 格式重构

### 新格式（purpose.md）

```markdown
# Purpose

- 探索世界中各场所的独特功能
- 理解 buff 效果与日常行为的关系
- 尝试与其他角色建立互动
```

**规则：**
- 只有活跃条目，无状态标记
- Dream 对 Purpose 的操作：增加条目、修改条目、删除条目
- 没有"已完成"概念，方向性目标通过修改或删除来演进
- Planner 读取全部条目作为规划依据

### 对现有代码的影响

- `store.read_purpose()` / `store.reset_purpose()`：兼容新格式（读写字符串即可，列表格式由 LLM 自行处理）
- Planner system prompt 中 Purpose 部分：直接显示 purpose.md 全文，无需格式转换

---

## 六、Agent 身份修正

### 问题

当前 Planner 的 system prompt 为"你是小明的规划助手"，导致 LLM 以第三人称视角思考，将小明视为被操控的对象。

### 修改

**plan.py：**
- system prompt 改为"你是小明"
- 规划语境改为第一人称（"我现在的目标是……"）

**think.py：**
- 检查并确保 system prompt 及 user prompt 均使用第一人称
- Think 阶段 Thought 输出应为"我"视角

---

## 七、文件改动清单

| 文件 | 改动类型 | 主要内容 |
|---|---|---|
| `agent/memory/store.py` | 修改 | 新增 consolidated 相关函数，last_dream_time 读写，隐去索引函数 |
| `agent/dream.py` | **新建** | DreamConfig、DreamTrigger、Dream 类 |
| `agent/loop.py` | 修改 | Plan 完成后插入 dream 触发检测 |
| `agent/plan.py` | 修改 | Planner 身份 prompt 修正 |
| `agent/think.py` | 修改 | Think 第一人称检查 |
| `agent/config.py` | 修改 | 读取 dream 配置字段 |
| `agent/ui_server.py` | 修改 | dream 事件日志样式，dreaming badge，接口扩展 |
| `profiles/*/memory/purpose.md` | 修改 | 格式改为多条目列表 |
| `memory/consolidated/`（目录） | **新建** | 整合记忆存放目录 |

---

## 八、开发顺序

```
Step 1  Purpose 格式重构 + Agent 身份修正（影响 plan.py / think.py / purpose.md）
   ↓
Step 2  store.py 记忆系统扩展（consolidated 函数 / last_dream_time / hide_from_index）
   ↓
Step 3  dream.py 新建（DreamConfig / DreamTrigger / Dream 四步流程）
   ↓
Step 4  loop.py 集成（Plan 完成后检测触发）
   ↓
Step 5  config.py 扩展（读取 dream 配置）
   ↓
Step 6  ui_server.py 更新（dream 日志展示 / dreaming 状态 / 接口扩展）
```

Step 1 和 Step 2 相互独立，可并行开发。

---

## 九、检验方案

### 9.1 Step 1 检验：Purpose 格式 + 身份修正

**检验点：**

- [ ] `purpose.md` 内容为多条目列表格式，无状态标记
- [ ] `store.read_purpose()` 正确读取并返回多条目内容
- [ ] Planner 的 LLM 日志中 system prompt 显示"你是小明"而非"规划助手"
- [ ] Think 阶段 Thought 输出中使用"我"而非"用户"或"小明"（手动运行一轮观察日志）

### 9.2 Step 2 检验：store.py 扩展

**检验点（可用单元测试或手动调用）：**

- [ ] `create_consolidated_memory()` 在 `memory/consolidated/` 下创建文件，格式含 Sources 字段
- [ ] `update_consolidated_memory()` 追加 Sources 并更新 Importance（= 原值 + 新增来源 importance 之和）
- [ ] `hide_from_index(paths)` 执行后：Memory.md 中对应条目消失，原始文件仍在磁盘
- [ ] `write_last_dream_time()` / `read_last_dream_time()` 读写一致，时区正确
- [ ] `get_memories_since(dt)` 仅返回时间戳晚于 dt 的记忆

### 9.3 Step 3 检验：dream.py

**触发逻辑检验：**

- [ ] `memory_count=-1` 时，该条件永不触发
- [ ] `time_minutes=-1` 时，该条件永不触发
- [ ] 三个条件均禁用时，`should_dream()` 永远返回 False
- [ ] 满足任一启用条件时，`should_dream()` 返回 True

**流程检验（手动触发 dream 观察日志）：**

- [ ] Step 1（阅读）：日志可见读取的记忆文件数量
- [ ] Step 2（整合）：
  - 新建整合记忆时：文件出现在 `consolidated/`，来源原始记忆从 Memory.md 消失，文件仍在磁盘
  - 更新整合记忆时：Sources 列表增加，Importance 更新
  - Memory.md 中整合记忆条目正确出现
- [ ] Step 3（提炼）：生成的高阶 recognition 含 Sources 字段，原始来源记忆仍在 Memory.md
- [ ] Step 4（Purpose 更新）：
  - `keep` 时 purpose.md 不变
  - `modify` / `replace` 时 purpose.md 内容正确更新
  - LLM 输出结构化 JSON 被正确解析

### 9.4 Step 4 检验：loop.py 集成

- [ ] dream 触发标志在 Plan 执行中被设置后，不立即打断当前 Plan
- [ ] 当前 Plan `plan_finish` 后进入 dream，loop 输出区出现 `dream_start` 日志
- [ ] Dream 结束后 loop 正常继续下一轮

### 9.5 Step 6 检验：UI

- [ ] loop 输出区能看到 `dream_start` / `dream_step` / `dream_end` 的样式化日志
- [ ] 状态 badge 在 dream 期间显示"做梦中"（或类似）状态
- [ ] `/loop-status` 接口返回中包含 `last_dream_time` 字段

### 9.6 端到端回归检验

运行 agent 至少两个完整 dream 周期，检查：

- [ ] Memory.md 条目数量在每次 dream 后减少（整合效果）
- [ ] `consolidated/` 目录下有文件出现
- [ ] Purpose 在第二次 dream 后有实质性变化（非简单重复）
- [ ] Thought 日志中 agent 以第一人称思考（无"用户"字样）
- [ ] 无无限循环：agent 完成 Purpose 相关探索后，dream 后 Purpose 更新为新方向

---

*最后更新：2026-05-30*
