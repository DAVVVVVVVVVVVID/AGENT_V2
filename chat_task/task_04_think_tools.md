# Task 04: Think 工具扩展（主动发起对话）

## 目标

在 Think 的工具集中新增两个对话相关工具：`find_nearby_players` 和 `send_chat_request`，使 agent 能够主动发起对话。同时在 Execute 中注册对应 handler。

## 依赖

Task 01（Sandbox API 必须提供 `/chat/nearby` 和 `/chat/request` 端点）。

## 涉及文件

- `agent/think.py`（在 `_TOOLS` 列表中新增两个工具定义）
- `agent/execute.py`（在 `_HANDLERS` 中注册两个 handler）
- `agent/sandbox_client.py`（新增两个调用方法）

---

## 新增工具定义（think.py）

### `find_nearby_players`

插入到 `_TOOLS` 列表中（建议放在 `record_recognition` 之前）：

```python
{
    "type": "function",
    "function": {
        "name": "find_nearby_players",
        "description": (
            "查询当前所在 Arena 内可以发起对话的其他 Player 列表。"
            "返回 entity_id、名字和所在 arena_id。"
            "在主动发起对话前，先调用此工具确认目标是否在附近。"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
},
```

### `send_chat_request`

```python
{
    "type": "function",
    "function": {
        "name": "send_chat_request",
        "description": (
            "向一个或多个 Player 发起对话邀请。"
            "对方会收到请求通知并决定是否接受。"
            "greeting 是你的开场白，应该自然且符合当前情境。"
            "调用后可继续执行其他行动；对方是否接受由系统在下一轮处理。"
            "注意：主动发起对话后通常应立即调用 finish() 结束当前 Plan，"
            "以便系统切换到对话等待状态。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "to_entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要邀请对话的 entity_id 列表（通常一个）",
                },
                "greeting": {
                    "type": "string",
                    "description": "开场白，对方将看到这句话",
                },
            },
            "required": ["to_entity_ids", "greeting"],
        },
    },
},
```

---

## 新增 SandboxClient 方法

```python
def get_chat_nearby(self, entity_id: str) -> dict:
    return self._get("/chat/nearby", params={"entity_id": entity_id})

def post_chat_request(self, from_entity_id: str, to_entity_ids: list[str], greeting: str) -> dict:
    return self._post("/chat/request", json={
        "from_entity_id": from_entity_id,
        "to_entity_ids": to_entity_ids,
        "greeting": greeting,
    })
```

---

## 新增 Execute Handler（execute.py）

```python
def _find_nearby_players(self, args: dict) -> dict:
    data = self._client.get_chat_nearby(self._eid)
    players = data.get("players", [])
    if not players:
        return _ok({"players": [], "message": "附近没有其他 Player"})
    desc = "、".join(f"{p['name']}（{p['entity_id']}）" for p in players)
    return _ok({"players": players, "message": f"附近有 {len(players)} 位：{desc}"})

def _send_chat_request(self, args: dict) -> dict:
    to_ids = args["to_entity_ids"]
    greeting = args["greeting"]
    try:
        data = self._client.post_chat_request(self._eid, to_ids, greeting)
        return _ok({
            "request_id": data["request_id"],
            "message": f"已向 {len(to_ids)} 位发送对话邀请",
        })
    except Exception as e:
        return _fail(f"发送对话请求失败：{e}")
```

在 `_HANDLERS` 字典末尾（`finish` 之前）注册：

```python
"find_nearby_players": Execute._find_nearby_players,
"send_chat_request":   Execute._send_chat_request,
```

---

## 实现注意事项

1. **`find_nearby_players` 无参数**：entity_id 由 Execute 实例的 `self._eid` 提供，不需要 agent 显式传入。
2. **`send_chat_request` 的后续行为**：工具描述中已提示"通常应随后调用 finish()"，但这是建议而非强制。Loop 集成（Task 07）会处理发出邀请后的等待逻辑。
3. **不在此任务中处理等待**：发起请求后 agent 看到的结果是"已发送邀请"，对话是否建立由 Task 07 的 Loop 层检查。
4. **`_VALID_TOOL_NAMES` 无需手动维护**：它由 `{t["function"]["name"] for t in _TOOLS}` 生成，添加工具到 `_TOOLS` 后自动包含。

---

## 验收标准

- [ ] `find_nearby_players` 在 Think 的工具提示中可见
- [ ] `send_chat_request` 在 Think 的工具提示中可见
- [ ] Execute 能正确执行 `find_nearby_players`，同一 Arena 有人时返回列表，没人时返回 `[]`
- [ ] Execute 能正确执行 `send_chat_request`，成功时返回 `request_id`
- [ ] 两个工具均注册在 `_HANDLERS` 中，调用未知工具时不影响现有逻辑
