# Task 03: Perceive 扩展

## 目标

让 Perceive 模块在每次感知时同时拉取当前的待处理对话请求，并将结果暴露在 `perceive()` 的返回值中，使 Loop 层能感知到"有人想和我说话"。

## 依赖

Task 01（Sandbox API 必须提供 `/chat/pending` 端点）。

## 涉及文件

- `agent/perceive.py`（主要修改文件）
- `agent/sandbox_client.py`（新增 `get_chat_pending()` 方法）

---

## 需要新增的方法

### `SandboxClient.get_chat_pending(entity_id)`

```python
def get_chat_pending(self, entity_id: str) -> dict:
    return self._get("/chat/pending", params={"entity_id": entity_id})
```

返回格式与 Task 01 中 `GET /chat/pending` 一致：

```json
{
    "requests": [
        {
            "request_id": "...",
            "from_entity_id": "...",
            "from_name": "...",
            "greeting": "..."
        }
    ]
}
```

---

## 需要修改的函数

### `Perceive.perceive()`

在现有 `env + player` 拉取之后，增加对 `/chat/pending` 的调用：

```python
try:
    pending_raw = self._client.get_chat_pending(self._entity_id)
    pending_requests = pending_raw.get("requests", [])
except Exception:
    pending_requests = []
```

返回字典中新增字段：

```python
return {
    "arena_tree":           env["arena_tree"],
    "vision_tiles":         env["vision_tiles"],
    "front_object":         env["front_object"],
    "player_state":         player,
    "state_diff":           diff,
    "pending_chat_requests": pending_requests,   # 新增
}
```

---

## 实现注意事项

1. **异常容忍**：`/chat/pending` 失败时不中断 perceive，返回空列表即可。这是辅助信息，不影响主循环感知。
2. **不做过滤**：store 层只返回原始数据，过滤/判断逻辑放在 Task 05（Judgment Module）。
3. **`in_chat_room` 不需要单独字段**：已有 `player_state.buffs` 中的 `chat_active` 表示当前在聊天室，Loop 层直接检查即可。
4. **不修改 `_MONITORED`**：state_diff 只跟踪内部 player 状态，pending_requests 是外部状态，不参与 diff 计算。

---

## 验收标准

- [ ] `perceive()` 返回值包含 `pending_chat_requests` 字段（无请求时为空列表 `[]`）
- [ ] 有待处理请求时，字段包含 `request_id`、`from_entity_id`、`from_name`、`greeting`
- [ ] `/chat/pending` 调用失败（如沙盒未实现）时不抛出异常，静默返回 `[]`
- [ ] 现有测试（若有）不因此修改而中断
