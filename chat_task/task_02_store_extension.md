# Task 02: Store 扩展（Chat 记忆）

## 目标

在 `agent/memory/store.py` 中新增 `chat` 类型记忆的支持，包括目录初始化、文件创建、索引更新，以及让 Dream 触发计数包含 chat 记忆。

## 依赖

无（与 Task 01 并行）。

## 涉及文件

- `agent/memory/store.py`（主要修改文件）
- `agent/ui_server.py`（记忆清除逻辑，需同步添加 chat 类型的清除支持）

---

## Chat 记忆文件格式

存储位置：`memory/chats/chat_NNN.md`

```
---
Type: chat
Participants: [entity_id_1, entity_id_2]
Time: 2026-06-01T00:00:00+00:00
Summary: 一句话概括
Importance: 5
Keywords: [关键词1, 关键词2]
---

## 主题
聊了什么，为什么开始这次对话

## 关键信息
对方透露的重要信息，或对我有参考价值的内容（没有则写"无"）

## 结果
对话如何结束，是否影响当前计划或目标
```

**不存储原始对话记录**：内容由对话整理模块提炼，不是逐字记录。

---

## 需要新增的函数

### `create_chat_memory()`

```python
def create_chat_memory(
    participants: list[str],     # entity_id 列表
    summary: str,
    topic: str,                  # ## 主题 的内容
    key_info: str,               # ## 关键信息 的内容
    outcome: str,                # ## 结果 的内容
    importance: int,
    keywords: list[str],
) -> Path:
```

- 在 `_CHATS_DIR` 下创建 `chat_NNN.md`，NNN 自增
- 写入 frontmatter 和三个 section
- 调用 `update_memory_index()` 和 `update_keywords()`
- 返回文件路径

### `get_chats_dir()`

```python
def get_chats_dir() -> Path:
```

返回 `_CHATS_DIR`，与 `get_events_dir()` 等保持风格一致。

### `clear_chats()`

```python
def clear_chats() -> int:
```

删除 `chats/` 下所有 `.md` 文件，返回删除数量。供 UI 记忆清除功能调用。

---

## 需要修改的函数

### `init()`

新增全局变量 `_CHATS_DIR`，并在 `init()` 中初始化：

```python
_CHATS_DIR = base / "chats"
_CHATS_DIR.mkdir(parents=True, exist_ok=True)
```

### `get_new_memory_count(since)`

当前只统计 events 和 recognitions，需新增对 chats 的统计：

```python
for directory in (_EVENTS_DIR, _RECOGNITIONS_DIR, _CHATS_DIR):
    ...
```

### `get_memories_since(since)`

同上，chats 目录也纳入统计范围，供 Dream 触发计数使用。

### `delete_memory_file(path)`

在 `allowed` 判断中新增 `_CHATS_DIR`：

```python
allowed = (
    str(fp).startswith(str(events_dir))
    or str(fp).startswith(str(recognitions_dir))
    or str(fp).startswith(str(consolidated_dir))
    or str(fp).startswith(str(chats_dir))   # 新增
)
```

---

## UI Server 同步修改

`ui_server.py` 的 `/memory/clear` 端点需要新增 `chat` 类型的处理：

```python
if "chat" in types:
    cleared["chat"] = store.clear_chats()
```

Memory viewer sidebar 也需要添加 `💬 Chat` 导航项（此部分可以在 Task 10 一起处理，但在 store 层先实现 `get_chats_dir()` 供其调用）。

---

## 实现注意事项

1. **Participants 格式**：frontmatter 中 `Participants` 字段存 entity_id 列表，不是名字。名字可能会改变，entity_id 是稳定标识
2. **文件编号**：`chat_NNN.md` 使用三位数字，与 event/recog 风格一致，不足三位补零
3. **Keywords 来源**：由对话整理模块（Task 08）提供，store 层只负责写入，不自行生成
4. **Importance 范围**：与 event 一致，0–10 整数

---

## 验收标准

- [ ] `store.init()` 执行后，`memory/chats/` 目录自动创建
- [ ] `create_chat_memory()` 能正确生成格式合规的文件，写入 Memory.md 和 keywords.md
- [ ] `get_new_memory_count()` 返回值包含 chats 目录中符合时间范围的文件数
- [ ] `get_memories_since()` 返回值包含 chats 目录中符合时间范围的路径
- [ ] `clear_chats()` 删除 chats 下所有 md 文件并返回正确数量
- [ ] `delete_memory_file("chats/chat_001.md")` 成功执行，不抛权限错误
