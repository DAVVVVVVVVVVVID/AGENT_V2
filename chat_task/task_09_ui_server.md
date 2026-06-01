# Task 09: UI Server 扩展

## 目标

扩展 `agent/ui_server.py`，支持以下功能：
1. 人类观察者（Human Observer）加入聊天室，能查看实时对话
2. 人类以 Player 身份在聊天室中发言
3. `/memory/clear` 支持 `chat` 类型
4. `/memory/files` 支持 `type=chats` 参数
5. 新增 WebSocket 推送对话相关事件

## 依赖

Task 01（Sandbox API 必须实现所有 `/chat/*` 端点）。

## 涉及文件

- `agent/ui_server.py`（主要修改文件）

---

## 修改一：`/memory/clear` 支持 chat

在现有的 `memory_clear()` 函数中，在 `if "purpose" in types:` 之前添加：

```python
if "chat" in types:
    from agent.memory.store import clear_chats
    summary["chat"] = clear_chats()
```

同时在 `"all"` 快捷值中加入 `"chat"`：

```python
if "all" in types:
    types = ["events", "recognitions", "consolidated", "auxiliary", "purpose", "chat"]
```

---

## 修改二：`/memory/files` 支持 chats

在 `memory_files()` 函数中，扩展 `if/elif` 判断：

```python
elif type == "chats":
    directory = store.get_chats_dir()
```

并在返回时补充 `Participants`、`Summary`、`Time` 等 chat 特有字段的解析（与 events 类似，从 frontmatter 读取）。

---

## 修改三：emit 函数透传对话事件

现有 `emit()` 函数已将所有 emit 消息推入 `_msg_queue`，无需修改。但 WebSocket 的 `_stream_events()` 需要能处理以下新事件类型并转发给前端：

| 事件类型 | 前端用途 |
|---------|---------|
| `chat_judgment` | 显示接受/拒绝决策 |
| `chat_session_start` | 打开对话面板 |
| `chat_speak` | 显示 agent 发言 |
| `chat_wait` | 显示等待状态 |
| `chat_event` | 显示对方退出 |
| `chat_exit` | 对话结束 |
| `chat_session_end` | 关闭对话面板 |
| `chat_memory_saved` | 显示记忆已保存 |
| `chat_reorient` | 显示重新定向结果 |
| `chat_done_replan` | 触发重新规划提示 |

这些事件类型已在现有的 `ws_events` WebSocket 端点的广播逻辑中自动透传（因为它们都通过 `_msg_queue` 传递），前端通过 `msg.type` 字段区分处理。如有特定格式需求，在前端（Task 10）中处理即可。

---

## 新增 HTTP 端点

### `GET /chat/nearby`

人类 UI 查询当前 agent 附近可对话的 Player：

```python
@app.get("/chat/nearby")
def ui_chat_nearby() -> dict:
    try:
        return _client.get_chat_nearby(_player_id)
    except Exception as e:
        return {"error": str(e), "players": []}
```

### `POST /chat/request`

UI 代表人类 Player 发起对话请求：

```python
@app.post("/chat/request")
def ui_chat_request(body: dict) -> dict:
    to_entity_ids = body.get("to_entity_ids", [])
    greeting = body.get("greeting", "你好！")
    try:
        return _client.post_chat_request(
            from_entity_id=_player_id,
            to_entity_ids=to_entity_ids,
            greeting=greeting,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

### `GET /chat/room/{chat_room_id}`

UI 轮询聊天室状态（人类作为观察者或参与者）：

```python
@app.get("/chat/room/{chat_room_id}")
def ui_chat_room(chat_room_id: str, since_seq: int = 0) -> dict:
    try:
        return _client.get_chat_room(
            chat_room_id=chat_room_id,
            entity_id=_player_id,
            since_seq=since_seq,
        )
    except Exception as e:
        return {"error": str(e)}
```

### `POST /chat/message`

UI 代表人类 Player 在聊天室中发言：

```python
@app.post("/chat/message")
def ui_chat_message(body: dict) -> dict:
    chat_room_id = body.get("chat_room_id", "")
    content = body.get("content", "").strip()
    if not content:
        return {"ok": False, "reason": "content is empty"}
    try:
        return _client.post_chat_message(
            entity_id=_player_id,
            chat_room_id=chat_room_id,
            content=content,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

### `POST /chat/exit`

UI 代表人类 Player 退出聊天室：

```python
@app.post("/chat/exit")
def ui_chat_exit(body: dict) -> dict:
    chat_room_id = body.get("chat_room_id", "")
    try:
        return _client.post_chat_exit(
            entity_id=_player_id,
            chat_room_id=chat_room_id,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

### `GET /chat/status`

前端用于轮询当前 agent 是否处于对话状态：

```python
@app.get("/chat/status")
def ui_chat_status() -> dict:
    """返回 agent 当前的对话状态信息。"""
    try:
        player = _client.get_player(_player_id)
        buffs = player.get("buffs", [])
        in_chat = "chat_active" in buffs
    except Exception:
        in_chat = False
    
    return {
        "in_chat": in_chat,
        "chat_room_id": _shared_state.get("current_chat_room_id"),
    }
```

同时需要在 `_shared_state` 初始化中添加：

```python
_shared_state: dict = {
    ...
    "current_chat_room_id": None,   # 新增
}
```

并在 Loop 的 `_check_and_handle_chat` 进入聊天室时写入此值（需在 Task 07 中配合处理）。

---

## 实现注意事项

1. **人类以 `_player_id` 操作**：所有 UI 发起的对话 API 都使用 agent 自己的 `_player_id`，即人类接管了 agent 的 Player 身份。这意味着人类发起对话请求时，agent 的 Loop 应感知到 `chat_active` buff 并暂停。
2. **不新建 Human Player**：UI 不创建额外的观察者 entity，直接复用 agent 的身份。
3. **`/chat/status` 轮询频率**：前端每 2 秒调用一次，判断是否需要显示对话面板。
4. **错误处理**：沙盒 API 调用失败时返回 `{"error": "..."}` 而非抛出 500，保持 UI 可用。

---

## 验收标准

- [ ] `POST /memory/clear` 支持 `"chat"` 类型，返回删除数量
- [ ] `GET /memory/files?type=chats` 返回 chat 记忆列表
- [ ] `GET /chat/nearby` 返回附近 Player 列表
- [ ] `POST /chat/request` 能发起对话请求，返回 `request_id`
- [ ] `GET /chat/room/{id}` 能轮询到聊天室消息
- [ ] `POST /chat/message` 能在聊天室中发言
- [ ] `POST /chat/exit` 能退出聊天室
- [ ] `GET /chat/status` 正确反映 agent 当前是否处于对话状态
- [ ] 对话相关 emit 事件通过 WebSocket 正常推送到前端
