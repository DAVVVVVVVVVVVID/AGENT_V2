# Task 07: Loop 集成

## 目标

将对话系统（判断模块 + 对话循环模块）织入主循环 `loop.py`，使 agent 能在正常执行 Plan 的同时响应对话请求，并在对话结束后恢复执行。

## 依赖

- Task 03（Perceive 暴露 `pending_chat_requests`）
- Task 04（Think 工具：`find_nearby_players`、`send_chat_request`）
- Task 05（Judgment Module：`judge_chat_request`、`respond_to_request`）
- Task 06（Chat Session：`run_chat_session`、`ChatSessionResult`）

## 涉及文件

- `agent/loop.py`（主要修改文件）
- `agent/chat_aftermath.py`（Task 08 中实现，本任务预留调用点）

---

## 对话触发的两种路径

### 路径 A：被动触发（对方发起）

1. 每轮 Perceive 后，检查 `perceive_result["pending_chat_requests"]`
2. 若有待处理请求，暂停当前 Plan，调用 Judgment Module 决策
3. 若接受，等待沙盒创建聊天室（`chat_room_id` 返回），然后运行 ChatSession
4. 若拒绝，继续当前 Plan

### 路径 B：主动触发（自己发起）

1. agent 在 Plan 中调用 `send_chat_request()` 工具
2. Plan 随后调用 `finish()` 结束
3. 下一个外层循环迭代中，Perceive 会检测到 `chat_active` buff（若对方接受）
4. 若检测到 `chat_active` buff，说明已进入聊天室，直接运行 ChatSession

---

## 修改 `_run_plan`

在现有的 Perceive 步骤之后，插入对话请求检查：

```python
# ── Perceive ──────────────────────────────────────────────────────────
try:
    perceive_result = perceiver.perceive()
except Exception as e:
    ...

# ── Chat 请求检查（新增）─────────────────────────────────────────────
chat_result = _check_and_handle_chat(
    perceive_result=perceive_result,
    entity_id=perceiver._entity_id,
    client=executor._client,
    retriever=retriever,
    current_plan=plan,
    llm=llm,
    model=model,
    emit=emit,
    stop_flag=stop_flag,
    shared_state=shared_state,
)
if chat_result is not None:
    # 对话结束后，触发后处理，并中断当前 Plan
    _handle_chat_aftermath(chat_result, llm, model, emit, shared_state)
    return "__chat_interrupted__"
```

---

## 新增辅助函数

### `_check_and_handle_chat()`

```python
def _check_and_handle_chat(
    perceive_result: dict,
    entity_id: str,
    client,
    retriever,
    current_plan: str,
    llm,
    model: str,
    emit: Callable,
    stop_flag,
    shared_state,
) -> ChatSessionResult | None:
    """
    检查是否有待处理对话请求或当前是否在聊天室中。
    - 若无，返回 None（继续正常 Plan）
    - 若有请求且接受，运行 ChatSession，返回 ChatSessionResult
    - 若有请求但拒绝，返回 None
    """
    from agent.chat_judgment import judge_chat_request, respond_to_request, JudgmentResult
    from agent.chat_session import run_chat_session
    
    # ── 检查是否已在聊天室（路径 B：主动发起后对方已接受）──────────────
    buffs = perceive_result.get("player_state", {}).get("buffs", [])
    if "chat_active" in buffs:
        # 从 shared_state 中读取 pending_chat_room_id（由 execute 的 send_chat_request 写入）
        chat_room_id = (shared_state or {}).get("pending_chat_room_id")
        if chat_room_id:
            if shared_state is not None:
                del shared_state["pending_chat_room_id"]
            participants = perceive_result.get("player_state", {}).get("chat_participants", [])
            cfg = (shared_state or {}).get("cfg", {})
            return run_chat_session(
                entity_id=entity_id,
                chat_room_id=chat_room_id,
                participants=participants,
                client=client,
                llm=llm,
                model=model,
                personality=cfg.get("personality", ""),
                purpose=store.read_purpose(),
                emit=emit,
                stop_flag=stop_flag,
            )
    
    # ── 检查被动请求 ──────────────────────────────────────────────────
    pending = perceive_result.get("pending_chat_requests", [])
    if not pending:
        return None
    
    # 只处理第一个请求（多个请求按先后顺序处理，其余轮次再处理）
    request = pending[0]
    
    # 用发起者 entity_id 检索记忆
    try:
        memories = retriever.retrieve(
            request["from_entity_id"],
            f"来自 {request['from_name']} 的对话",
        )
    except Exception:
        memories = []
    
    cfg = (shared_state or {}).get("cfg", {})
    
    judgment = judge_chat_request(
        entity_id=entity_id,
        request=request,
        perceive_result=perceive_result,
        memories=memories,
        personality=cfg.get("personality", ""),
        purpose=store.read_purpose(),
        current_plan=current_plan,
        llm=llm,
        model=model,
    )
    
    emit({"type": "chat_judgment", "accept": judgment.accept, "message": judgment.message})
    
    # 调用沙盒响应
    try:
        response = respond_to_request(client, entity_id, request["request_id"], judgment)
    except Exception as e:
        emit({"type": "warning", "content": f"响应对话请求失败：{e}"})
        return None
    
    if not judgment.accept:
        return None
    
    chat_room_id = response.get("chat_room_id")
    if not chat_room_id:
        # 状态为 "waiting"（多人邀请尚未全部响应），不立即进入对话
        emit({"type": "chat_waiting", "request_id": request["request_id"]})
        return None
    
    # 进入聊天室
    participants = response.get("participants", [entity_id, request["from_entity_id"]])
    return run_chat_session(
        entity_id=entity_id,
        chat_room_id=chat_room_id,
        participants=participants,
        client=client,
        llm=llm,
        model=model,
        personality=cfg.get("personality", ""),
        purpose=store.read_purpose(),
        emit=emit,
        stop_flag=stop_flag,
    )
```

### `_handle_chat_aftermath()`

```python
def _handle_chat_aftermath(
    chat_result: ChatSessionResult,
    llm,
    model: str,
    emit: Callable,
    shared_state: dict | None,
):
    """Task 08 中实现，此处预留调用点。"""
    try:
        from agent import chat_aftermath
        chat_aftermath.process(chat_result, llm, model, emit, shared_state)
    except ImportError:
        pass   # Task 08 未实现时静默跳过
    except Exception as e:
        emit({"type": "warning", "content": f"对话后处理失败：{e}"})
```

---

## 修改外层循环

在 `run()` 函数的内层 `for idx, plan in enumerate(plan_batch, 1)` 中，需要处理新的返回值 `"__chat_interrupted__"`：

```python
reply = _run_plan(...)

if reply == "__chat_interrupted__":
    # 对话结束后，重新从外层规划（不继续剩余 Plan）
    emit({"type": "chat_done_replan"})
    break   # 跳出内层 for 循环，外层 while True 自动重新规划
elif reply == "__interrupted__":
    store.set_plan_status(idx - 1, "interrupted")
    break
else:
    store.set_plan_status(idx - 1, "done")
```

---

## `send_chat_request` 的 chat_room_id 传递

Execute 的 `_send_chat_request` handler 在调用沙盒后，需要把 `request_id` 写入 `shared_state`，以便后续判断对方接受时能找到对应聊天室。

由于 Execute 不直接访问 `shared_state`，有两种方案：

**方案 A（推荐）**：Loop 在调用 `execute_sequence` 后，检查 snapshot 中是否有 `send_chat_request` 的成功结果，若有则读取 `request_id` 存入 `shared_state["pending_request_id"]`。下次 Perceive 检测到 `chat_active` buff 时，再查询请求状态获取 `chat_room_id`。

**方案 B**：给 Execute 传入 `shared_state` 引用（侵入性较高，不推荐）。

本任务推荐方案 A，在 `_run_plan` 的 Execute 步骤后增加如下逻辑：

```python
snapshot = executor.execute_sequence(action_sequence)

# 检查 send_chat_request 结果（新增）
for a in snapshot:
    if a["name"] == "send_chat_request" and a["status"] == "success":
        if shared_state is not None:
            shared_state["pending_request_id"] = a["result"].get("request_id")
```

---

## emit 新增事件

| 事件类型 | 说明 |
|---------|------|
| `chat_judgment` | 接受/拒绝决策，含 message |
| `chat_waiting` | 接受了但聊天室尚未创建（多人邀请等待中） |
| `chat_done_replan` | 对话结束，触发重新规划 |

---

## 实现注意事项

1. **不阻塞 stop_flag**：`run_chat_session` 接受 `stop_flag`，用户可以随时终止对话并停止 agent。
2. **重新规划 vs 恢复 Plan**：对话结束后一律重新规划（外层 while 重新 Perceive → Planner），不尝试恢复被中断的 Plan。原因：对话后世界状态可能已变化，继续旧 Plan 可能失效。
3. **多人邀请的等待**：若响应后状态为 `"waiting"`（对方尚未全部响应），本轮不进入对话，继续正常 Plan。下一轮 Perceive 时若沙盒已创建聊天室（触发 `chat_active` buff），再进入对话。
4. **Dream 触发时机**：对话后的 Dream 检查由 Task 08（chat_aftermath）负责，不在 Loop 层处理。

---

## 验收标准

- [ ] 有 pending 请求时，Loop 每轮 Perceive 后调用 Judgment Module
- [ ] 接受后成功进入 ChatSession，对话期间 Plan 执行暂停
- [ ] 拒绝后继续正常 Plan，不进入 ChatSession
- [ ] 对话结束（任意原因）后，Loop 重新进入规划阶段
- [ ] stop_flag 触发时 ChatSession 正常退出，Loop 不挂起
- [ ] `send_chat_request` 工具执行成功后 `request_id` 写入 `shared_state`
