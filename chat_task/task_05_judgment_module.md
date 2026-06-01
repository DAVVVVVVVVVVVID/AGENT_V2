# Task 05: 判断模块（Chat Judgment）

## 目标

实现 `agent/chat_judgment.py`，负责在收到对话请求时做出接受/拒绝决策。这是一个独立的轻量级 LLM 调用，与 Think 的行动规划完全解耦。

## 依赖

- Task 01（需要调用 `/chat/respond` 端点）
- Task 02（需要读取 chat 记忆辅助判断）

## 涉及文件

- `agent/chat_judgment.py`（新建）
- `agent/sandbox_client.py`（新增 `post_chat_respond()` 方法）

---

## 设计背景

对话请求判断被设计为独立模块，而非混入 Think 的 system prompt，原因：
- Think 的语义是"执行当前 Plan"，混入"要不要接受对话"会破坏其语义清晰性
- 判断逻辑简单（输出只有接受/拒绝 + 一句话），不需要多步 ReAct
- 独立模块更易于测试和调整判断策略

---

## 新建文件：`agent/chat_judgment.py`

### 数据结构

```python
from dataclasses import dataclass

@dataclass
class JudgmentResult:
    accept: bool
    message: str    # 接受时为回应话语，拒绝时为拒绝理由
```

### 主函数签名

```python
def judge_chat_request(
    entity_id: str,
    request: dict,              # 来自 perceive 的 pending_chat_requests 单条
    perceive_result: dict,      # 当前 perceive 结果
    memories: list[str],        # 已检索的记忆片段（可为空）
    personality: str,           # agent 性格描述（来自 config）
    purpose: str,               # 当前 Purpose 文本
    current_plan: str,          # 当前执行中的 Plan 描述
    llm,                        # OpenAI client
    model: str,
) -> JudgmentResult:
```

### Prompt 设计

**System prompt**（简短，专注判断）：

```
你是{agent_name}，正在{current_plan}。
性格：{personality}
当前目标（Purpose）：{purpose}

有人请求和你对话。请判断是否接受，并给出回应（接受时说欢迎/问候，拒绝时委婉说明）。

只输出 JSON：
{"accept": true/false, "message": "回应内容"}
```

**User message**：

```
来自 {from_name}（{from_entity_id}）的对话请求：
"{greeting}"

当前状态：{position_summary}
相关记忆：
{memories_text}

请决定是否接受。
```

### 实现细节

```python
import json
from agent.memory import store

def judge_chat_request(...) -> JudgmentResult:
    agent_name = store.read_config().get("name", entity_id)
    
    memories_text = "\n".join(f"- {m}" for m in memories) if memories else "（无相关记忆）"
    position = perceive_result.get("player_state", {}).get("position", "未知")
    
    system = (
        f"你是{agent_name}，正在{current_plan}。\n"
        f"性格：{personality}\n"
        f"当前目标：{purpose}\n\n"
        "有人请求和你对话。请判断是否接受，并给出一句话回应。\n"
        '只输出 JSON：{"accept": true/false, "message": "回应内容"}'
    )
    user = (
        f"来自 {request['from_name']}（{request['from_entity_id']}）的对话请求：\n"
        f'"{request["greeting"]}"\n\n'
        f"当前位置：{position}\n"
        f"相关记忆：\n{memories_text}\n\n"
        "请决定是否接受。"
    )
    
    resp = llm.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        response_format={"type": "json_object"},
        max_tokens=200,
    )
    
    raw = json.loads(resp.choices[0].message.content)
    return JudgmentResult(
        accept=bool(raw.get("accept", False)),
        message=str(raw.get("message", "")),
    )
```

### 辅助函数

```python
def respond_to_request(
    client,             # SandboxClient
    entity_id: str,
    request_id: str,
    result: JudgmentResult,
) -> dict:
    """调用 /chat/respond，返回沙盒响应"""
    return client.post_chat_respond(
        entity_id=entity_id,
        request_id=request_id,
        accept=result.accept,
        message=result.message,
    )
```

---

## 新增 SandboxClient 方法

```python
def post_chat_respond(
    self,
    entity_id: str,
    request_id: str,
    accept: bool,
    message: str,
) -> dict:
    return self._post("/chat/respond", json={
        "entity_id": entity_id,
        "request_id": request_id,
        "accept": accept,
        "message": message,
    })
```

---

## 判断策略说明

### 什么时候拒绝？

判断模块不写死拒绝规则，完全交给 LLM + prompt 决策。但 prompt 中提供了这些上下文辅助判断：
- 当前在做什么（current_plan）
- 总体目标（Purpose）
- 相关记忆（是否认识对方）
- 性格描述（内向 vs 外向）

### 记忆检索

调用方（Task 07）负责在调用 `judge_chat_request` 前完成记忆检索（以 `from_entity_id` 为查询词）。判断模块只负责消费 `memories` 参数，不自行检索。

---

## 实现注意事项

1. **JSON 解析失败兜底**：若 LLM 输出不是合法 JSON，默认拒绝（`accept=False`），message 为"抱歉，现在不方便"。
2. **`response_format` 限制**：`json_object` 模式要求 prompt 中必须含 "JSON" 字样，否则某些模型会报错。已在 system prompt 中包含。
3. **不引入重试**：判断是一次性决策，失败就拒绝，不重试 LLM。
4. **`store.read_config()` 用法**：此函数读取 agent 的 `config.yaml`，其中含 `name` 字段。如果调用方已有 config dict，可直接传入而不调用 store。

---

## 验收标准

- [ ] `judge_chat_request()` 对测试 prompt 能正确返回 `JudgmentResult(accept=True/False, message="...")`
- [ ] LLM 输出非 JSON 时函数不抛出异常，返回 `accept=False`
- [ ] `respond_to_request()` 正确调用沙盒 `/chat/respond` 端点
- [ ] 判断结果的 `message` 不为空（接受时为问候语，拒绝时为拒绝理由）
- [ ] 模块可独立 import，不依赖 Loop 或 Think 的任何状态
