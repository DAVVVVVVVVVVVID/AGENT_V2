# Task 08: 对话后处理（Chat Aftermath）

## 目标

实现 `agent/chat_aftermath.py`，在对话结束后完成记忆整理、Dream 检查和重新定向三步处理，使 agent 能从对话信息中学习并合理调整后续行动方向。

## 依赖

- Task 02（`create_chat_memory()`）
- Task 06（`ChatSessionResult`）
- Task 07（在 Loop 中调用 `process()`）

## 涉及文件

- `agent/chat_aftermath.py`（新建）

---

## 设计背景

对话后处理分三步，均在后台同步执行（不阻塞外层规划）：

1. **记忆整理**：将对话内容提炼成 chat 记忆文件（`memory/chats/chat_NNN.md`）
2. **Dream 检查**：调用 `dream_trigger.should_dream()`，若满足条件则触发 Dream
3. **重新定向**：轻量级 LLM 调用，判断是否需要更新 Purpose 或给出 Plan 建议

步骤 1-2 已有相应基础设施，步骤 3 是本任务的核心新增内容。

---

## 新建文件：`agent/chat_aftermath.py`

### 主函数

```python
def process(
    chat_result: ChatSessionResult,
    llm,
    model: str,
    emit: Callable[[dict], None],
    shared_state: dict | None = None,
) -> None:
    """
    对话结束后的三步处理。
    在 Loop 的 _handle_chat_aftermath 中调用。
    """
    emit({"type": "chat_aftermath_start"})
    
    # 步骤 1：记忆整理
    memory_path = _create_chat_memory(chat_result, llm, model, emit)
    
    # 步骤 2：Dream 检查
    if shared_state is not None:
        dream_trigger = shared_state.get("dream_trigger")
        dreamer = shared_state.get("dreamer")
        if dream_trigger is not None and dreamer is not None:
            if dream_trigger.should_dream():
                emit({"type": "dream_triggered_by_chat"})
                try:
                    dreamer.run()
                except Exception as e:
                    emit({"type": "warning", "content": f"Dream 失败：{e}"})
    
    # 步骤 3：重新定向
    _reorient(chat_result, llm, model, emit, shared_state)
    
    emit({"type": "chat_aftermath_done"})
```

---

### 步骤 1：记忆整理

```python
def _create_chat_memory(
    chat_result: ChatSessionResult,
    llm,
    model: str,
    emit: Callable,
) -> Path | None:
    """调用 LLM 提炼对话摘要，写入 chat 记忆文件。"""
    from agent.memory import store
    
    if not chat_result.messages:
        return None
    
    messages_text = "\n".join(
        f"{m['from_entity_id']}: {m['content']}" for m in chat_result.messages
    )
    
    system = (
        "你是对话记录整理助手。将以下对话整理成结构化信息。\n"
        "只输出 JSON，格式：\n"
        '{"summary": "一句话概括", "topic": "主题内容", '
        '"key_info": "关键信息（对我有价值的内容，无则写\'无\'）", '
        '"outcome": "对话如何结束，是否影响当前计划", '
        '"keywords": ["关键词1", "关键词2"], '
        '"importance": 整数0-10}'
    )
    
    try:
        resp = llm.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": f"对话记录：\n{messages_text}"},
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
        )
        raw = json.loads(resp.choices[0].message.content)
    except Exception as e:
        emit({"type": "warning", "content": f"记忆整理 LLM 调用失败：{e}"})
        raw = {
            "summary": "一次对话",
            "topic": messages_text[:200],
            "key_info": "无",
            "outcome": f"对话结束，原因：{chat_result.exit_reason}",
            "keywords": [],
            "importance": 3,
        }
    
    try:
        path = store.create_chat_memory(
            participants=chat_result.participants,
            summary=raw["summary"],
            topic=raw["topic"],
            key_info=raw["key_info"],
            outcome=raw["outcome"],
            importance=int(raw.get("importance", 3)),
            keywords=raw.get("keywords", []),
        )
        emit({"type": "chat_memory_saved", "path": str(path)})
        return path
    except Exception as e:
        emit({"type": "warning", "content": f"保存 chat 记忆失败：{e}"})
        return None
```

---

### 步骤 3：重新定向

```python
def _reorient(
    chat_result: ChatSessionResult,
    llm,
    model: str,
    emit: Callable,
    shared_state: dict | None,
) -> None:
    """
    轻量级 LLM 调用：判断对话后是否需要调整方向。
    结果写入 shared_state["reorient_hint"]，供外层规划参考。
    """
    from agent.memory import store
    
    purpose = store.read_purpose()
    cfg = (shared_state or {}).get("cfg", {})
    agent_name = cfg.get("name", "agent")
    
    messages_text = "\n".join(
        f"{m['from_entity_id']}: {m['content']}" for m in chat_result.messages[-10:]
    )
    
    system = (
        f"你是{agent_name}，刚刚完成了一段对话。\n"
        f"当前总体目标（Purpose）：{purpose}\n\n"
        "请根据对话内容，判断是否需要调整当前目标或接下来的行动方向。\n"
        "只输出 JSON：\n"
        '{"needs_reorient": true/false, '
        '"reason": "原因（如不需要调整则写\'无\' ）", '
        '"hint": "对下一个 Plan 的建议（如不需要则写\'继续原计划\'）"}'
    )
    
    try:
        resp = llm.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": f"刚才的对话（最近 10 条）：\n{messages_text}"},
            ],
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        raw = json.loads(resp.choices[0].message.content)
    except Exception as e:
        emit({"type": "warning", "content": f"重新定向 LLM 调用失败：{e}"})
        return
    
    emit({
        "type": "chat_reorient",
        "needs_reorient": raw.get("needs_reorient", False),
        "hint": raw.get("hint", "继续原计划"),
    })
    
    if shared_state is not None:
        shared_state["reorient_hint"] = raw.get("hint", "")
```

---

## `reorient_hint` 在 Loop 中的使用

`shared_state["reorient_hint"]` 由外层规划读取，在构建 Planner prompt 时加入提示：

**修改 `agent/plan.py`（或 Planner 的 generate 方法）**：

```python
# 在 Planner.generate() 的 system prompt 中添加
reorient_hint = shared_state.get("reorient_hint", "") if shared_state else ""
if reorient_hint and reorient_hint != "继续原计划":
    system += f"\n\n【刚完成一次对话，建议参考以下方向】：{reorient_hint}"
    # 使用后清除，避免影响后续 Planner
    if shared_state:
        shared_state.pop("reorient_hint", None)
```

---

## 实现注意事项

1. **全部异常要捕获**：记忆整理和重新定向的失败不应中断 Loop，只 emit warning。
2. **Dream 的 dream_trigger 和 dreamer 引用**：Loop 集成时需要把这两个对象放入 `shared_state`。需在 `loop.run()` 中补充：
   ```python
   if shared_state is not None:
       shared_state["dream_trigger"] = dream_trigger
       shared_state["dreamer"] = dreamer
   ```
3. **不更新 Purpose**：重新定向只生成 hint，不直接修改 Purpose 文件。Purpose 的更新由 Dream 模块负责（Dream 有完整的 Reflect + Update Purpose 流程）。
4. **记忆整理的 LLM 模型**：可以使用更轻量的模型（如 haiku）做摘要，从 `cfg` 中读取 `memory_model` 配置项（若无则 fallback 到主模型）。

---

## 验收标准

- [ ] 对话结束后，`memory/chats/` 下生成格式合规的 `chat_NNN.md` 文件
- [ ] 生成的 chat 记忆包含三个 section：主题、关键信息、结果
- [ ] LLM 调用失败时，仍生成一条简单的兜底记忆（不抛出异常）
- [ ] `shared_state["reorient_hint"]` 在对话有实质内容时被正确写入
- [ ] Dream 触发条件满足时，`dreamer.run()` 被调用
- [ ] 整个 `process()` 执行完毕后，Loop 继续正常规划（无阻塞）
