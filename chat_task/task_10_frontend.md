# Task 10: 前端 Chat UI

## 目标

在现有 UI 页面中加入对话相关界面，包括：
1. Memory 侧边栏新增 `💬 Chat` 导航项
2. 当 agent 收到对话请求时，在日志面板中显示判断结果
3. 对话活跃时显示聊天室面板，人类可以观察或参与
4. 对话结束后显示记忆已保存提示

## 依赖

Task 09（UI Server 必须提供 `/chat/*` 端点，且 WebSocket 推送对话事件）。

## 涉及文件

- `agent/ui_server.py` 中的 `_HTML` 字符串（整个前端内嵌在此处）

---

## 设计原则

- **不阻断主流程**：对话 UI 是可折叠的辅助面板，不占用主日志区域
- **轮询为主**：聊天室消息通过 `GET /chat/room/{id}?since_seq=N` 轮询，2 秒一次
- **WebSocket 触发**：对话事件通过 WebSocket 通知前端打开/关闭聊天面板

---

## 修改一：Memory 侧边栏新增 Chat 导航项

在 Memory Viewer 侧边栏的类型按钮列表中，在 `🔮 Consolidated` 之后添加：

```html
<button onclick="loadMemory('chats')" id="btn-chats">💬 Chat</button>
```

并在 `loadMemory()` JS 函数中处理 `chats` 类型的展示，frontmatter 显示 `Participants`、`Summary`、`Time`、`Importance` 字段。

---

## 修改二：日志面板渲染对话事件

在现有的 `renderMessage(msg)` 函数（或等效的 WebSocket 消息处理函数）中，新增以下事件类型的渲染：

```javascript
case "chat_judgment":
    appendLog(`💬 对话请求判断：${msg.accept ? "✅ 接受" : "❌ 拒绝"} — ${msg.message}`, "chat");
    break;

case "chat_session_start":
    appendLog(`💬 进入聊天室 ${msg.chat_room_id}`, "chat");
    openChatPanel(msg.chat_room_id);
    break;

case "chat_speak":
    appendLog(`💬 [我说] ${msg.content}`, "chat-speak");
    break;

case "chat_wait":
    appendLog(`💬 等待对方回应（第${msg.streak}次）`, "chat-wait");
    break;

case "chat_exit":
    appendLog(`💬 退出对话：${msg.reason}`, "chat");
    closeChatPanel();
    break;

case "chat_memory_saved":
    appendLog(`💬 对话记忆已保存：${msg.path}`, "chat");
    break;

case "chat_reorient":
    if (msg.needs_reorient) {
        appendLog(`💬 重新定向建议：${msg.hint}`, "chat-reorient");
    }
    break;

case "chat_done_replan":
    appendLog(`💬 对话结束，重新规划中…`, "chat");
    break;
```

---

## 新增三：聊天室面板（Chat Panel）

### HTML 结构

在主内容区域下方（或侧边）添加可折叠的聊天面板：

```html
<div id="chat-panel" style="display:none;" class="chat-panel">
  <div class="chat-panel-header">
    <span>💬 聊天室</span>
    <span id="chat-room-id-label" style="font-size:12px;color:#888;"></span>
    <button onclick="sendChatMessage()">发送</button>
    <button onclick="exitChatRoom()">退出</button>
    <button onclick="closeChatPanel()">收起</button>
  </div>
  <div id="chat-messages" class="chat-messages"></div>
  <div class="chat-input-row">
    <input type="text" id="chat-input" placeholder="输入消息..." 
           onkeydown="if(event.key==='Enter') sendChatMessage()">
  </div>
</div>
```

### CSS

```css
.chat-panel {
    position: fixed;
    bottom: 0;
    right: 20px;
    width: 380px;
    height: 320px;
    background: #1e1e2e;
    border: 1px solid #444;
    border-radius: 8px 8px 0 0;
    display: flex;
    flex-direction: column;
    z-index: 1000;
}
.chat-panel-header {
    background: #2d2d3f;
    padding: 8px 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    border-radius: 8px 8px 0 0;
}
.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 8px 12px;
    font-size: 13px;
    line-height: 1.5;
}
.chat-msg-self   { color: #89b4fa; text-align: right; }
.chat-msg-other  { color: #cdd6f4; }
.chat-msg-system { color: #6c7086; font-style: italic; font-size: 11px; }
.chat-input-row {
    padding: 6px 8px;
    display: flex;
    gap: 6px;
    border-top: 1px solid #333;
}
.chat-input-row input {
    flex: 1;
    background: #313244;
    border: 1px solid #555;
    border-radius: 4px;
    color: #cdd6f4;
    padding: 4px 8px;
    font-size: 13px;
}
```

### JavaScript

```javascript
let _chatRoomId = null;
let _chatSinceSeq = 0;
let _chatPollTimer = null;
const _myEntityId = "";  // 从 /agent-config 获取后填入

function openChatPanel(roomId) {
    _chatRoomId = roomId;
    _chatSinceSeq = 0;
    document.getElementById("chat-panel").style.display = "flex";
    document.getElementById("chat-room-id-label").textContent = roomId;
    document.getElementById("chat-messages").innerHTML = "";
    if (_chatPollTimer) clearInterval(_chatPollTimer);
    _chatPollTimer = setInterval(pollChatRoom, 2000);
}

function closeChatPanel() {
    document.getElementById("chat-panel").style.display = "none";
    if (_chatPollTimer) { clearInterval(_chatPollTimer); _chatPollTimer = null; }
}

async function pollChatRoom() {
    if (!_chatRoomId) return;
    try {
        const res = await fetch(`/chat/room/${_chatRoomId}?since_seq=${_chatSinceSeq}`);
        const data = await res.json();
        if (data.status === "closed") {
            appendChatMsg("（聊天室已关闭）", "system");
            closeChatPanel();
            return;
        }
        for (const msg of (data.messages || [])) {
            const isSelf = msg.from_entity_id === _myEntityId;
            appendChatMsg(
                `${isSelf ? "我" : msg.from_entity_id}: ${msg.content}`,
                isSelf ? "self" : "other",
            );
            _chatSinceSeq = Math.max(_chatSinceSeq, msg.seq);
        }
        for (const evt of (data.events || [])) {
            if (evt.type === "player_exit") {
                appendChatMsg(`${evt.entity_id} 离开了对话`, "system");
            }
            _chatSinceSeq = Math.max(_chatSinceSeq, evt.seq);
        }
    } catch(e) {
        // 静默忽略轮询错误
    }
}

function appendChatMsg(text, type) {
    const div = document.getElementById("chat-messages");
    const p = document.createElement("p");
    p.className = `chat-msg-${type}`;
    p.style.margin = "3px 0";
    p.textContent = text;
    div.appendChild(p);
    div.scrollTop = div.scrollHeight;
}

async function sendChatMessage() {
    const input = document.getElementById("chat-input");
    const content = input.value.trim();
    if (!content || !_chatRoomId) return;
    input.value = "";
    try {
        await fetch("/chat/message", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({chat_room_id: _chatRoomId, content}),
        });
    } catch(e) {
        appendChatMsg(`发送失败：${e}`, "system");
    }
}

async function exitChatRoom() {
    if (!_chatRoomId) return;
    try {
        await fetch("/chat/exit", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({chat_room_id: _chatRoomId}),
        });
    } catch(e) {}
    closeChatPanel();
}

// 页面加载时获取 entity_id
fetch("/agent-config")
    .then(r => r.json())
    .then(cfg => { window._myEntityId = cfg.entity_id; });
```

---

## 修改四：状态轮询显示 Chat 状态

在现有的状态轮询（`/loop-status`）旁边，增加对 `/chat/status` 的查询，在页面顶部显示对话状态徽章：

```javascript
// 在现有 pollStatus() 或等效函数中添加
fetch("/chat/status")
    .then(r => r.json())
    .then(data => {
        const badge = document.getElementById("chat-status-badge");
        if (data.in_chat) {
            badge.textContent = "💬 对话中";
            badge.style.display = "inline";
            if (data.chat_room_id && _chatRoomId !== data.chat_room_id) {
                openChatPanel(data.chat_room_id);
            }
        } else {
            badge.style.display = "none";
        }
    });
```

在页面 header 中添加徽章元素：

```html
<span id="chat-status-badge" style="display:none; 
      background:#89b4fa; color:#1e1e2e; 
      padding:2px 8px; border-radius:10px; font-size:12px;"></span>
```

---

## 实现注意事项

1. **`_myEntityId` 初始化**：JavaScript 中用 `window._myEntityId` 存储，通过 `/agent-config` 接口获取，页面加载时异步填充。
2. **聊天面板的打开时机**：有两个触发路径：① WebSocket 收到 `chat_session_start` 事件；② `/chat/status` 轮询检测到 `in_chat=true`。两者都调用 `openChatPanel()`，函数内部做幂等处理。
3. **滚动行为**：每次追加消息后自动滚动到底部（`div.scrollTop = div.scrollHeight`）。
4. **面板关闭不等于退出**：点击"收起"只隐藏面板不调用 `/chat/exit`，点击"退出"才真正退出聊天室。
5. **Memory Viewer 中 chat 类型**：frontmatter 中 `Participants` 是 JSON 数组字符串，显示时需要处理方括号。

---

## 验收标准

- [ ] Memory 侧边栏有 `💬 Chat` 按钮，点击后加载 chat 记忆列表
- [ ] WebSocket 收到 `chat_session_start` 时聊天面板自动弹出
- [ ] 聊天面板正确显示来自 agent 和其他 entity 的消息（颜色区分）
- [ ] 人类可在输入框中发言，消息正常发送到聊天室
- [ ] 点击"退出"正确调用 `/chat/exit` 并关闭面板
- [ ] 对话中页面顶部显示 `💬 对话中` 徽章
- [ ] 日志中显示 `chat_judgment`、`chat_speak`、`chat_memory_saved` 等事件
- [ ] `/chat/status` 轮询检测到 `in_chat=true` 时自动打开面板
