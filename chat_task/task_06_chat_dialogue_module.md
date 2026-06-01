# Task 06: 对话循环模块（Chat Session）

## 目标

实现 `agent/chat_session.py`，负责管理 agent 进入聊天室后的全过程：轮询消息、决定发言/等待/退出，直到对话结束。

## 依赖

- Task 01（轮询 `/chat/room/{id}`、发言 `/chat/message`、退出 `/chat/exit`）
- Task 02（对话结束后调用 `create_chat_memory()`）

## 涉及文件

- `agent/chat_session.py`（新建）
- `agent/sandbox_client.py`（新增三个调用方法）

---

## 设计背景

对话循环被设计为独立模块而非复用 Think，原因：
- Think 的工具集面向"在世界中行动"，对话工具（speak/wait/exit）语义完全不同
- 对话有独特的轮询机制（seq 增量拉取），不适合放在 ReAct 循环中
- 独立模块便于未来扩展（如多轮策略、话题引导等）

---

## 新增 SandboxClient 方法

```python
def get_chat_room(self, chat_room_id: str, entity_id: str, since_seq: int = 0) -> dict:
    return self._get(
        f"/chat/room/{chat_room_id}",
        params={"entity_id": entity_id, "since_seq": since_seq},
    )

def post_chat_message(self, entity_id: str, chat_room_id: str, content: str) -> dict:
    return self._post("/chat/message", json={
        "entity_id": entity_id,
        "chat_room_id": chat_room_id,
        "content": content,
    })

def post_chat_exit(self, entity_id: str, chat_room_id: str) -> dict:
    return self._post("/chat/exit", json={
        "entity_id": entity_id,
        "chat_room_id": chat_room_id,
    })
```

---

## 新建文件：`agent/chat_session.py`

### 数据结构

```python
from dataclasses import dataclass, field

@dataclass
class ChatSessionResult:
    chat_room_id: str
    participants: list[str]         # 参与者 entity_id 列表
    messages: list[dict]            # 完整消息列表（全量，非增量）
    exit_reason: str                # "finished" | "timeout" | "room_closed" | "error"
    duration_rounds: int            # 经历的轮次数
```

### 核心常量

```python
_POLL_INTERVAL = 2.0        # 秒，轮询间隔
_MAX_WAIT_STREAK = 3        # 连续等待次数后触发中立提示
_MAX_ROUNDS = 50            # 对话最大轮次（防无限循环）
```

### 主函数签名

```python
def run_chat_session(
    entity_id: str,
    chat_room_id: str,
    participants: list[str],    # 初始参与者列表（含自身）
    client,                     # SandboxClient
    llm,                        # OpenAI client
    model: str,
    personality: str,
    purpose: str,
    emit: Callable[[dict], None],
    stop_flag: threading.Event | None = None,
) -> ChatSessionResult:
```

### 对话 LLM 的工具定义

```python
_SESSION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "speak",
            "description": "发送一条消息到聊天室。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要说的内容"}
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": (
                "等待对方发言，不发送任何消息。"
                "适用于：刚说完一句话后等待回应；或对方话题未说完时。"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "exit_chat",
            "description": (
                "结束并退出本次对话。"
                "适用于：话题已告一段落；或对话已无继续必要。"
                "退出前应说一句告别语（单独调用 speak，再调用 exit_chat）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "退出原因简述（仅内部记录用）"}
                },
                "required": ["reason"],
            },
        },
    },
]
```

### System Prompt 模板

```python
_SESSION_SYSTEM = """\
你是{agent_name}，正在参与一场对话。
性格：{personality}
当前总体目标：{purpose}

对话室中的参与者：{participants_str}

你的行动选项：
- speak(content)：说一句话
- wait()：等待对方回应
- exit_chat(reason)：结束对话

对话原则：
- 自然流畅，符合你的性格
- 每次轮到你时只做一个动作（speak 或 wait 或 exit_chat）
- 连续等待超过 {max_wait} 次后，应主动说话或退出
- 对话完成目的或自然结束时，用 exit_chat 退出
"""
```

### 主循环逻辑

```python
def run_chat_session(...) -> ChatSessionResult:
    all_messages: list[dict] = []
    since_seq = 0
    wait_streak = 0
    round_num = 0
    
    emit({"type": "chat_session_start", "chat_room_id": chat_room_id})
    
    while True:
        if stop_flag is not None and stop_flag.is_set():
            _safe_exit(client, entity_id, chat_room_id)
            return ChatSessionResult(..., exit_reason="stopped")
        
        if round_num >= _MAX_ROUNDS:
            _safe_exit(client, entity_id, chat_room_id)
            return ChatSessionResult(..., exit_reason="timeout")
        
        # 1. 轮询房间状态
        import time
        time.sleep(_POLL_INTERVAL)
        
        try:
            room = client.get_chat_room(chat_room_id, entity_id, since_seq)
        except Exception as e:
            emit({"type": "chat_warning", "content": f"轮询失败：{e}"})
            continue
        
        if room["status"] == "closed":
            return ChatSessionResult(..., exit_reason="room_closed")
        
        # 2. 处理新消息和事件
        new_msgs = room.get("messages", [])
        new_evts = room.get("events", [])
        all_messages.extend(new_msgs)
        
        if new_msgs:
            since_seq = max(m["seq"] for m in new_msgs)
        if new_evts:
            since_seq = max(since_seq, max(e["seq"] for e in new_evts))
        
        for evt in new_evts:
            if evt["type"] == "player_exit":
                emit({"type": "chat_event", "event": evt})
        
        # 3. 决策：是否该我发言？
        # 若最后一条消息不是我发的，或者等待超时，就做决策
        last_sender = all_messages[-1]["from_entity_id"] if all_messages else None
        i_should_respond = (last_sender != entity_id) or (wait_streak >= _MAX_WAIT_STREAK)
        
        if not i_should_respond:
            wait_streak += 1
            round_num += 1
            continue
        
        # 4. LLM 决策
        decision = _think_in_session(
            entity_id, all_messages, participants,
            personality, purpose, wait_streak, llm, model,
        )
        
        if decision["action"] == "speak":
            content = decision["content"]
            try:
                res = client.post_chat_message(entity_id, chat_room_id, content)
                all_messages.append({
                    "seq": res["seq"],
                    "from_entity_id": entity_id,
                    "content": content,
                })
                since_seq = max(since_seq, res["seq"])
                wait_streak = 0
                emit({"type": "chat_speak", "content": content})
            except Exception as e:
                emit({"type": "chat_warning", "content": f"发言失败：{e}"})
        
        elif decision["action"] == "wait":
            wait_streak += 1
            emit({"type": "chat_wait", "streak": wait_streak})
        
        elif decision["action"] == "exit_chat":
            emit({"type": "chat_exit", "reason": decision.get("reason", "")})
            client.post_chat_exit(entity_id, chat_room_id)
            return ChatSessionResult(
                chat_room_id=chat_room_id,
                participants=participants,
                messages=all_messages,
                exit_reason="finished",
                duration_rounds=round_num,
            )
        
        round_num += 1
```

### `_think_in_session` 辅助函数

```python
def _think_in_session(
    entity_id, all_messages, participants,
    personality, purpose, wait_streak, llm, model,
) -> dict:
    """一次 LLM 调用，返回 {"action": "speak"|"wait"|"exit_chat", "content": str, "reason": str}"""
    from agent.memory import store
    agent_name = store.read_config().get("name", entity_id)
    
    participants_str = "、".join(
        p if p != entity_id else f"{p}（你）" for p in participants
    )
    
    # 如果连续等待次数达到阈值，在 user 消息中加入中立提示
    neutral_hint = ""
    if wait_streak >= _MAX_WAIT_STREAK:
        neutral_hint = f"\n（你已等待了 {wait_streak} 次，请考虑主动开口或结束对话。）"
    
    history_text = "\n".join(
        f"{m['from_entity_id']}: {m['content']}" for m in all_messages[-20:]
    ) or "（对话刚开始，还没有消息）"
    
    system = _SESSION_SYSTEM.format(
        agent_name=agent_name,
        personality=personality,
        purpose=purpose,
        participants_str=participants_str,
        max_wait=_MAX_WAIT_STREAK,
    )
    
    resp = llm.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": f"对话记录：\n{history_text}{neutral_hint}\n\n请选择你的下一个行动。"},
        ],
        tools=_SESSION_TOOLS,
        tool_choice="required",
        max_tokens=300,
    )
    
    tc = resp.choices[0].message.tool_calls[0]
    name = tc.function.name
    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
    
    if name == "speak":
        return {"action": "speak", "content": args.get("content", "")}
    elif name == "wait":
        return {"action": "wait"}
    elif name == "exit_chat":
        return {"action": "exit_chat", "reason": args.get("reason", "")}
    else:
        return {"action": "wait"}   # 兜底
```

---

## emit 事件类型

| 事件类型 | 说明 |
|---------|------|
| `chat_session_start` | 进入聊天室 |
| `chat_speak` | 我发言了 |
| `chat_wait` | 我选择等待 |
| `chat_event` | 有人退出房间 |
| `chat_exit` | 我主动退出 |
| `chat_warning` | 轮询/发言失败 |
| `chat_session_end` | 对话结束（携带 exit_reason） |

---

## 实现注意事项

1. **消息历史截断**：传给 LLM 的历史消息最多 20 条，避免 context 过长。
2. **`_safe_exit`**：被 stop_flag 打断时调用，忽略其异常，确保不阻塞线程退出。
3. **轮询间隔**：`_POLL_INTERVAL=2.0` 秒，沙盒是本地进程，2 秒足够。生产环境可配置。
4. **`since_seq` 初始值**：从 0 开始，第一次拉取获取所有历史（包括接受后立即产生的第一条消息）。
5. **等待策略**：连续 3 次等待后触发"中立提示"（不是强制行为，LLM 仍可选择 wait），由 LLM 自行判断是否主动说话。

---

## 验收标准

- [ ] `run_chat_session()` 可独立调用，不依赖 Loop 状态
- [ ] `speak` 行动后消息正确出现在 all_messages 中
- [ ] `wait` 行动后 wait_streak 递增
- [ ] 连续 wait ≥ 3 次时，LLM prompt 中含中立提示
- [ ] `exit_chat` 行动后调用沙盒 `/chat/exit`，函数正常返回 `ChatSessionResult`
- [ ] 房间状态变为 `closed` 时，函数自动返回 `exit_reason="room_closed"`
- [ ] `max_rounds=50` 超限时，调用 exit 并返回 `exit_reason="timeout"`
