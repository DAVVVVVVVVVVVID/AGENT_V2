# Task 01: Sandbox API 扩展

## 目标

在 BASIC_SANDBOX 中新增对话系统所需的全部 API 端点，并同步更新 `../SANDBOX/docs/api-spec.md`。

本任务是整个 Chat 模块的基础，所有后续任务均依赖此任务完成。

## 依赖

无。

## 涉及文件

- `../SANDBOX/` 服务端代码（具体文件视沙盒实现而定）
- `../SANDBOX/docs/api-spec.md`（**必须同步更新**，见 CLAUDE.md 要求）

---

## 新增状态

沙盒需要维护以下两类新状态：

### 对话请求（ChatRequest）

```
{
    request_id: str,
    from_entity_id: str,
    to_entity_ids: [str],       # 被邀请的 player 列表
    greeting: str,
    status: "pending" | "active" | "rejected" | "expired",
    accepted_ids: [str],        # 已接受的 player
    rejected_ids: [str],        # 已拒绝的 player
    chat_room_id: str | null    # 创建聊天室后填入
}
```

### 聊天室（ChatRoom）

```
{
    chat_room_id: str,
    participants: [str],        # 当前仍在房间内的 entity_id 列表
    messages: [
        { seq: int, from_entity_id: str, content: str, timestamp: str }
    ],
    events: [
        { seq: int, type: "player_exit", entity_id: str, timestamp: str }
    ],
    status: "active" | "closed"
}
```

---

## 新增 API 端点

### 1. 查询附近可对话 Player

```
GET /chat/nearby
Query: entity_id=<str>
Response: {
    "players": [
        { "entity_id": str, "name": str, "arena_id": str }
    ]
}
```

**范围规则**：与请求方 entity_id 处于同一 Arena 的其他 player（排除自身）。

---

### 2. 发起对话请求

```
POST /chat/request
Body: {
    "from_entity_id": str,
    "to_entity_ids": [str],    # 可以是多个
    "greeting": str
}
Response: {
    "request_id": str
}
```

---

### 3. 查询待处理的对话请求

```
GET /chat/pending
Query: entity_id=<str>
Response: {
    "requests": [
        {
            "request_id": str,
            "from_entity_id": str,
            "from_name": str,
            "greeting": str
        }
    ]
}
```

此接口由 Perceive 模块调用（见 Task 03）。

---

### 4. 响应对话请求

```
POST /chat/respond
Body: {
    "entity_id": str,
    "request_id": str,
    "accept": bool,
    "message": str    # 接受时为回应话语，拒绝时为拒绝理由
}
Response: {
    "chat_room_id": str | null,    # 接受且聊天室已创建时返回
    "status": "waiting" | "room_created" | "rejected"
}
```

**聊天室创建时机**：
- 若 to_entity_ids 只有一个，且该 player 接受，立即创建聊天室
- 若 to_entity_ids 有多个，当发起者 + 至少一个被邀请者都完成响应后，将所有接受者放入同一聊天室

---

### 5. 查询聊天室状态（轮询用）

```
GET /chat/room/{chat_room_id}
Query: entity_id=<str>&since_seq=<int>
Response: {
    "status": "active" | "closed",
    "participants": [str],
    "messages": [
        { "seq": int, "from_entity_id": str, "from_name": str, "content": str, "timestamp": str }
    ],
    "events": [
        { "seq": int, "type": "player_exit", "entity_id": str, "name": str, "timestamp": str }
    ]
}
```

`since_seq` 用于增量拉取，只返回 seq > since_seq 的消息和事件。

---

### 6. 在聊天室发言

```
POST /chat/message
Body: {
    "entity_id": str,
    "chat_room_id": str,
    "content": str
}
Response: { "seq": int }
```

---

### 7. 退出聊天室

```
POST /chat/exit
Body: {
    "entity_id": str,
    "chat_room_id": str
}
Response: { "room_closed": bool }
```

退出后从 participants 中移除该 entity_id。若 participants 为空，room status 变为 "closed"。

---

## Buff 系统

进入聊天室（POST /chat/respond 接受后）时，对该 player 施加以下 buff：

| buff 名称 | 效果 |
|-----------|------|
| `chat_active` | 无法移动（move_to_tile / move_direction / move_to_area 均失败） |
| `chat_active` | 无法使用物品（use_object 失败） |
| `chat_active` | 无法退出物品（leave_object 失败） |

退出聊天室（POST /chat/exit）后移除 `chat_active` buff。

**注意**：buff 应体现在 Perceive 的 `player_state.buffs` 字段中，使 agent 能感知到自己处于对话状态。

---

## 请求超时处理

当 to_entity_ids 包含多个 player 时，设置请求超时（建议 60 秒）。超时后未响应的 player 视为隐式拒绝，已接受的 player 正常进入聊天室。

---

## 实现注意事项

1. **request_id 和 chat_room_id** 使用 UUID 或自增 ID，全局唯一
2. **并发安全**：多个 player 同时响应同一请求时需加锁或使用原子操作
3. **孤立聊天室**：若发起者自己退出后聊天室只剩一人，不强制关闭，由剩余 player 自行退出
4. **范围判断**：`/chat/nearby` 查询时使用 arena_id 比较，不依赖坐标距离计算

---

## 验收标准

- [ ] 所有 7 个端点均可正常响应，返回格式符合规范
- [ ] 发起请求 → 接受 → 聊天室创建的完整流程可通过 curl 手动测试
- [ ] 发起请求 → 拒绝的流程正常，双方均无聊天室创建
- [ ] 多人邀请：部分接受、部分拒绝时，接受者正确进入同一聊天室
- [ ] 接受后 player 的 buff 列表中包含 `chat_active`，退出后移除
- [ ] `/chat/room/{id}?since_seq=N` 的增量拉取返回正确（seq > N 的内容）
- [ ] `api-spec.md` 已更新，包含所有新增端点的完整说明
