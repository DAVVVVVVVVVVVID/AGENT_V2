"""
Agent UI server — web dashboard for running and monitoring the agent.

Usage:
    uv run python -m agent.ui_server
    then open http://localhost:8001
"""

from __future__ import annotations

import json
import queue
import threading

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from openai import OpenAI

from agent.config import AGENT_CONFIG
from agent.sandbox_client import SandboxClient
from agent.perceive import Perceive
from agent.think import Think
from agent.execute import Execute
from agent.loop import run as run_loop
from agent.personality import ocean_to_description
from agent.logger import AgentLogger

app = FastAPI()

_cfg    = AGENT_CONFIG
_client = SandboxClient()

# ── loop state ────────────────────────────────────────────────────────────────
_loop_thread: threading.Thread | None = None
_stop_flag  = threading.Event()
_pause_flag = threading.Event()
_pause_flag.set()                          # set = running (not paused)
_msg_queue: queue.Queue[dict] = queue.Queue()
_shared_state: dict = {"history": [], "perceive": None, "task": ""}

# ── logging state ─────────────────────────────────────────────────────────────
_logging_enabled              = False
_current_logger: AgentLogger | None = None


def _run_loop_thread(task: str) -> None:
    global _current_logger
    _shared_state["task"] = task

    # create logger if logging is enabled
    logger: AgentLogger | None = None
    if _logging_enabled:
        logger = AgentLogger(task, _cfg)
        _current_logger = logger
        _msg_queue.put({"type": "log_start", "path": logger.path})

    perceiver = Perceive(_client, vision_size=_cfg["vision_size"])
    thinker   = Think(
        name=_cfg["name"],
        ocean=_cfg["ocean"],
        lifestyle=_cfg["lifestyle"],
        common_sense=_cfg.get("common_sense", []),
        llm_base_url=_cfg["llm_base_url"],
        model=_cfg["model"],
        agent_logger=logger,
    )
    executor = Execute(_client, entity_id=_cfg["entity_id"])

    def emit(msg: dict) -> None:
        if _stop_flag.is_set():
            raise InterruptedError("loop stopped by user")
        _msg_queue.put(msg)
        if logger:
            if msg.get("type") == "round_start":
                logger.log_round(msg["round"])
            else:
                logger.log_emit(msg)

    try:
        run_loop(task, perceiver, thinker, executor, emit=emit,
                 pause_flag=_pause_flag, shared_state=_shared_state)
    except InterruptedError:
        _msg_queue.put({"type": "warning", "content": "循环已手动停止。"})
        if logger:
            logger.log_emit({"type": "warning", "content": "循环已手动停止。"})
    except Exception as e:
        _msg_queue.put({"type": "warning", "content": f"循环异常：{e}"})
        if logger:
            logger.log_emit({"type": "warning", "content": f"循环异常：{e}"})
    finally:
        _msg_queue.put({"type": "loop_end"})
        if logger:
            logger.close()
            _current_logger = None


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(_HTML)


@app.get("/agent-config")
def agent_config() -> dict:
    cfg = _cfg
    return {
        "name":         cfg["name"],
        "entity_id":    cfg["entity_id"],
        "ocean":        cfg["ocean"],
        "ocean_desc":   ocean_to_description(
            cfg["ocean"]["O"], cfg["ocean"]["C"], cfg["ocean"]["E"],
            cfg["ocean"]["A"], cfg["ocean"]["N"],
        ),
        "lifestyle":    cfg["lifestyle"],
        "common_sense": cfg.get("common_sense", []),
        "model":        cfg["model"],
        "vision_size":  cfg["vision_size"],
    }


@app.get("/player-status")
def player_status() -> dict:
    try:
        return _client.get_player()
    except Exception as e:
        return {"error": str(e)}


@app.post("/run")
def run_task(body: dict) -> dict:
    global _loop_thread
    task = body.get("task", "").strip()
    if not task:
        return {"ok": False, "reason": "task is empty"}
    if _loop_thread and _loop_thread.is_alive():
        return {"ok": False, "reason": "loop already running"}
    _stop_flag.clear()
    _pause_flag.set()
    while not _msg_queue.empty():
        _msg_queue.get_nowait()
    _loop_thread = threading.Thread(target=_run_loop_thread, args=(task,), daemon=True)
    _loop_thread.start()
    return {"ok": True}


@app.post("/stop")
def stop_loop() -> dict:
    _stop_flag.set()
    _pause_flag.set()   # unblock if currently paused
    return {"ok": True}


@app.get("/logging")
def get_logging() -> dict:
    return {
        "enabled":  _logging_enabled,
        "log_path": _current_logger.path if _current_logger else None,
    }


@app.post("/logging")
def set_logging(body: dict) -> dict:
    global _logging_enabled
    _logging_enabled = bool(body.get("enabled", False))
    return {
        "enabled":  _logging_enabled,
        "log_path": _current_logger.path if _current_logger else None,
    }


@app.post("/pause")
def pause_loop() -> dict:
    if not (_loop_thread and _loop_thread.is_alive()):
        return {"ok": False, "reason": "no loop running"}
    _pause_flag.clear()
    return {"ok": True}


@app.post("/resume")
def resume_loop() -> dict:
    _pause_flag.set()
    return {"ok": True}


@app.post("/chat")
def chat_message(body: dict) -> dict:
    message = body.get("message", "").strip()
    inject  = body.get("inject", False)
    if not message:
        return {"ok": False, "reason": "message is empty"}

    cfg     = _cfg
    history = list(_shared_state.get("history", []))   # copy for reading
    task    = _shared_state.get("task", "")

    history_lines: list[str] = []
    for i, h in enumerate(history, 1):
        history_lines += [
            f"第{i}轮：",
            f"  思考：{h['thought']}",
            f"  行动：{h['action']}",
            f"  观察：{h['observation']}",
        ]
    history_text = "\n".join(history_lines) if history_lines else "（暂无历史记忆）"

    system = (
        f"你是{cfg['name']}，一个生活在虚拟世界中的角色。\n"
        f"当前任务：{task}\n\n"
        "现在任务已暂停，用户正在与你对话。\n"
        "请用自然语言回答用户的问题（解释你的思路、行动原因等），不要使用 tool call。\n"
        "如果用户给你提供指引，请表示理解，并说明你将如何据此调整后续行动。"
    )
    user_msg = f"【历史记忆】\n{history_text}\n\n【用户的话】\n{message}"

    llm = OpenAI(base_url=cfg["llm_base_url"], api_key="ollama")
    try:
        resp = llm.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
        )
        reply = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return {"ok": False, "reason": str(e)}

    if inject:
        # append to the shared list — same object as loop's history variable
        _shared_state["history"].append({
            "thought":     "（用户在此介入提供了指引）",
            "action":      "（用户介入）",
            "observation": f"用户指引：{message}",
        })
        _msg_queue.put({"type": "user_inject", "content": message})

    if _current_logger:
        _current_logger.log_chat(message, reply, inject)

    return {"ok": True, "reply": reply}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    import asyncio
    await ws.accept()
    try:
        while True:
            try:
                msg = _msg_queue.get_nowait()
                await ws.send_text(json.dumps(msg, ensure_ascii=False))
            except queue.Empty:
                await asyncio.sleep(0.1)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass


# ── embedded HTML ─────────────────────────────────────────────────────────────

_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>Agent Control Panel</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; height: 100vh; display: flex; flex-direction: column; }

  header { padding: 12px 20px; background: #1a1d27; border-bottom: 1px solid #2d3148; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 16px; font-weight: 600; color: #a78bfa; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #4b5563; flex-shrink: 0; }
  .status-dot.running { background: #10b981; box-shadow: 0 0 6px #10b981; animation: pulse 1.2s infinite; }
  .status-dot.paused  { background: #f59e0b; box-shadow: 0 0 6px #f59e0b; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
  .log-toggle-wrap { margin-left: auto; display: flex; align-items: center; gap: 10px; }
  .log-toggle-label { font-size: 12px; color: #6b7280; white-space: nowrap; }
  .toggle { position: relative; display: inline-block; width: 36px; height: 20px; flex-shrink: 0; }
  .toggle input { opacity: 0; width: 0; height: 0; }
  .toggle-slider { position: absolute; cursor: pointer; inset: 0; background: #374151; border-radius: 20px; transition: .2s; }
  .toggle-slider:before { position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px; background: #fff; border-radius: 50%; transition: .2s; }
  .toggle input:checked + .toggle-slider { background: #6d28d9; }
  .toggle input:checked + .toggle-slider:before { transform: translateX(16px); }
  #log-path-display { font-size: 11px; color: #4b5563; font-family: monospace; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #log-path-display.active { color: #34d399; }

  .main { flex: 1; display: grid; grid-template-columns: 280px 240px 1fr; gap: 0; overflow: hidden; }
  .panel { border-right: 1px solid #1e2235; display: flex; flex-direction: column; overflow: hidden; }
  .panel:last-child { border-right: none; }
  .panel-title { padding: 10px 14px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: #6b7280; background: #13161f; border-bottom: 1px solid #1e2235; flex-shrink: 0; }
  .panel-body { flex: 1; min-height: 0; overflow-y: auto; padding: 12px 14px; font-size: 13px; }
  .panel-body::-webkit-scrollbar { width: 4px; }
  .panel-body::-webkit-scrollbar-thumb { background: #2d3148; border-radius: 2px; }

  /* agent config */
  .field { margin-bottom: 14px; }
  .field label { display: block; font-size: 11px; color: #6b7280; margin-bottom: 4px; }
  .field .val { color: #e2e8f0; line-height: 1.5; }
  .field .val.mono { font-family: monospace; font-size: 12px; color: #93c5fd; }
  .ocean-bar { display: flex; align-items: center; gap: 8px; margin: 3px 0; }
  .ocean-bar span:first-child { width: 16px; font-size: 11px; color: #9ca3af; }
  .ocean-bar span:last-child { font-size: 11px; color: #9ca3af; width: 28px; text-align: right; }
  .bar-track { flex: 1; height: 6px; background: #1e2235; border-radius: 3px; overflow: hidden; }
  .bar-fill { height: 100%; background: #6d28d9; border-radius: 3px; }
  .list-item { padding: 3px 0; color: #d1d5db; border-bottom: 1px solid #1a1d27; font-size: 12px; line-height: 1.5; }
  .list-item:last-child { border-bottom: none; }

  /* player status */
  .stat { display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-bottom: 1px solid #1a1d27; }
  .stat:last-child { border-bottom: none; }
  .stat .key { font-size: 12px; color: #6b7280; }
  .stat .val { font-size: 12px; color: #e2e8f0; font-family: monospace; }
  .bar-wrap { display: flex; align-items: center; gap: 6px; }
  .mini-bar { width: 60px; height: 5px; background: #1e2235; border-radius: 3px; overflow: hidden; }
  .mini-fill { height: 100%; border-radius: 3px; }
  .hp-fill { background: #ef4444; }
  .en-fill { background: #f59e0b; }

  /* loop log */
  .log-entry { margin-bottom: 12px; border-left: 3px solid #2d3148; padding-left: 10px; }
  .log-entry.round       { border-color: #4b5563; }
  .log-entry.thought     { border-color: #6d28d9; }
  .log-entry.action      { border-color: #0284c7; }
  .log-entry.observation { border-color: #059669; }
  .log-entry.finish      { border-color: #d97706; }
  .log-entry.warning     { border-color: #dc2626; }
  .log-entry.inject      { border-color: #0891b2; }
  .log-tag { font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 3px; }
  .log-entry.round       .log-tag { color: #9ca3af; }
  .log-entry.thought     .log-tag { color: #a78bfa; }
  .log-entry.action      .log-tag { color: #38bdf8; }
  .log-entry.observation .log-tag { color: #34d399; }
  .log-entry.finish      .log-tag { color: #fbbf24; }
  .log-entry.warning     .log-tag { color: #f87171; }
  .log-entry.inject      .log-tag { color: #22d3ee; }
  .log-text { font-size: 12px; color: #d1d5db; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }

  /* chat section */
  #chat-section { display: none; flex-direction: column; flex: 0 0 300px; overflow: hidden; border-top: 2px solid #f59e0b55; }
  #chat-section.visible { display: flex; }
  .chat-header { padding: 8px 14px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; background: #13161f; border-bottom: 1px solid #1e2235; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; color: #f59e0b; }
  .chat-pause-badge { font-size: 10px; background: #78350f44; padding: 2px 7px; border-radius: 10px; }
  #chat-messages { flex: 1; height: 0; overflow-y: auto; padding: 10px 14px; display: flex; flex-direction: column; gap: 8px; }
  #chat-messages::-webkit-scrollbar { width: 4px; }
  #chat-messages::-webkit-scrollbar-thumb { background: #2d3148; border-radius: 2px; }
  .chat-bubble { max-width: 90%; padding: 8px 12px; border-radius: 10px; font-size: 12px; line-height: 1.6; word-break: break-word; }
  .chat-user  { align-self: flex-end; background: #3b1f6e; color: #e9d5ff; border-bottom-right-radius: 3px; }
  .chat-agent { align-self: flex-start; background: #1a2035; color: #d1d5db; border: 1px solid #2d3148; border-bottom-left-radius: 3px; }
  .chat-inject-tag { font-size: 10px; color: #22d3ee; margin-top: 6px; padding-top: 5px; border-top: 1px solid #2d3148; }
  .chat-input-row { padding: 8px 14px; background: #13161f; border-top: 1px solid #1e2235; display: flex; gap: 8px; align-items: center; flex-shrink: 0; }
  #chat-input { flex: 1; background: #0f1117; border: 1px solid #2d3148; border-radius: 6px; padding: 6px 10px; color: #e2e8f0; font-size: 13px; outline: none; }
  #chat-input:focus { border-color: #6d28d9; }
  .inject-label { display: flex; align-items: center; gap: 4px; font-size: 11px; color: #9ca3af; cursor: pointer; white-space: nowrap; user-select: none; }
  #inject-cb { accent-color: #6d28d9; cursor: pointer; }
  #btn-chat-send { padding: 6px 14px; background: #6d28d9; color: #fff; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; white-space: nowrap; }
  #btn-chat-send:hover { background: #7c3aed; }
  #btn-chat-send:disabled { background: #374151; color: #6b7280; cursor: not-allowed; }

  /* footer controls */
  footer { padding: 12px 16px; background: #1a1d27; border-top: 1px solid #2d3148; display: flex; gap: 10px; align-items: center; }
  footer input { flex: 1; background: #0f1117; border: 1px solid #2d3148; border-radius: 6px; padding: 8px 12px; color: #e2e8f0; font-size: 14px; outline: none; }
  footer input:focus { border-color: #6d28d9; }
  footer button { padding: 8px 18px; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; }
  #btn-run   { background: #6d28d9; color: #fff; }
  #btn-run:hover   { background: #7c3aed; }
  #btn-run:disabled   { background: #374151; color: #6b7280; cursor: not-allowed; }
  #btn-pause { background: #78350f; color: #fcd34d; }
  #btn-pause:hover   { background: #92400e; }
  #btn-pause.resume  { background: #064e3b; color: #6ee7b7; }
  #btn-pause.resume:hover { background: #065f46; }
  #btn-pause:disabled { background: #1f2937; color: #4b5563; cursor: not-allowed; }
  #btn-stop  { background: #7f1d1d; color: #fca5a5; }
  #btn-stop:hover  { background: #991b1b; }
  #btn-stop:disabled  { background: #1f2937; color: #4b5563; cursor: not-allowed; }
</style>
</head>
<body>

<header>
  <div class="status-dot" id="status-dot"></div>
  <h1>Agent Control Panel</h1>
  <span id="status-text" style="font-size:12px;color:#6b7280;">空闲</span>
  <div class="log-toggle-wrap">
    <span class="log-toggle-label">记录日志</span>
    <label class="toggle" title="开启后每次运行会写入 logs/ 目录">
      <input type="checkbox" id="log-toggle" onchange="setLogging(this.checked)">
      <span class="toggle-slider"></span>
    </label>
    <span id="log-path-display"></span>
  </div>
</header>

<div class="main">

  <!-- Agent 参数 -->
  <div class="panel">
    <div class="panel-title">Agent 参数</div>
    <div class="panel-body" id="agent-panel">加载中…</div>
  </div>

  <!-- Player 状态 -->
  <div class="panel">
    <div class="panel-title">Player 状态</div>
    <div class="panel-body" id="player-panel">加载中…</div>
  </div>

  <!-- Loop 输出 + 对话 -->
  <div class="panel">
    <div class="panel-title">Loop 输出</div>
    <div class="panel-body" id="log-panel"></div>

    <!-- 对话面板（暂停时显示） -->
    <div id="chat-section">
      <div class="chat-header">
        <span>对话</span>
        <span class="chat-pause-badge">⏸ 已暂停</span>
      </div>
      <div id="chat-messages"></div>
      <div class="chat-input-row">
        <input type="text" id="chat-input" placeholder="输入你的问题或指令…"
               onkeydown="if(event.key==='Enter'&&!event.shiftKey)sendChat()" />
        <label class="inject-label" title="将你的消息注入 Agent 记忆，下一轮生效">
          <input type="checkbox" id="inject-cb"> 注入记忆
        </label>
        <button id="btn-chat-send" onclick="sendChat()">发送</button>
      </div>
    </div>
  </div>

</div>

<footer>
  <input id="task-input" type="text" placeholder="输入任务目标，例如：去沙发上休息"
         onkeydown="if(event.key==='Enter')startRun()" />
  <button id="btn-run"   onclick="startRun()">运行</button>
  <button id="btn-pause" disabled onclick="togglePause()">暂停</button>
  <button id="btn-stop"  disabled onclick="stopRun()">停止</button>
</footer>

<script>
const logPanel    = document.getElementById('log-panel')
const statusDot   = document.getElementById('status-dot')
const statusText  = document.getElementById('status-text')
const btnRun      = document.getElementById('btn-run')
const btnPause    = document.getElementById('btn-pause')
const btnStop     = document.getElementById('btn-stop')
const chatSection = document.getElementById('chat-section')
let ws = null
let loopState = 'idle'  // 'idle' | 'running' | 'paused'

// ── logging toggle ────────────────────────────────────────────────────────────
fetch('/logging').then(r => r.json()).then(renderLogStatus)

function setLogging(enabled) {
  fetch('/logging', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({enabled}),
  }).then(r => r.json()).then(renderLogStatus)
}

function renderLogStatus(d) {
  document.getElementById('log-toggle').checked = d.enabled
  const el = document.getElementById('log-path-display')
  if (d.log_path) {
    const fname = d.log_path.split('/').pop()
    el.textContent = fname
    el.className   = 'active'
    el.title       = d.log_path
  } else {
    el.textContent = d.enabled ? '下次运行时生效' : ''
    el.className   = ''
    el.title       = ''
  }
}

// ── agent config (static) ────────────────────────────────────────────────────
fetch('/agent-config').then(r => r.json()).then(cfg => {
  const panel = document.getElementById('agent-panel')
  const ocean = cfg.ocean
  const bars  = ['O','C','E','A','N'].map(k => `
    <div class="ocean-bar">
      <span>${k}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${ocean[k]}%"></div></div>
      <span>${ocean[k]}</span>
    </div>`).join('')
  const lifestyle = cfg.lifestyle.map(s => `<div class="list-item">· ${s}</div>`).join('')
  const sense     = cfg.common_sense.map(s => `<div class="list-item">· ${s}</div>`).join('')
  panel.innerHTML = `
    <div class="field"><label>名称</label><div class="val">${cfg.name}</div></div>
    <div class="field"><label>实体 ID</label><div class="val mono">${cfg.entity_id}</div></div>
    <div class="field"><label>模型</label><div class="val mono">${cfg.model}</div></div>
    <div class="field"><label>视野范围</label><div class="val">${cfg.vision_size}×${cfg.vision_size}</div></div>
    <div class="field"><label>OCEAN</label>${bars}</div>
    <div class="field"><label>生活方式</label>${lifestyle}</div>
    <div class="field"><label>常识</label>${sense}</div>
  `
})

// ── player status (polling) ──────────────────────────────────────────────────
function renderPlayer(p) {
  if (p.error) {
    document.getElementById('player-panel').innerHTML = `<span style="color:#f87171">${p.error}</span>`
    return
  }
  const pos    = p.position ? `(${p.position.x}, ${p.position.y})` : '-'
  const fmap   = {up:'上',down:'下',left:'左',right:'右'}
  const facing = fmap[p.facing] || p.facing || '-'
  const hp     = p.hp ?? 0
  const en     = p.energy ?? 0
  const state  = p.state || '-'
  const label  = p.stateLabel ? `<br><span style="color:#fbbf24;font-size:11px">${p.stateLabel}</span>` : ''
  const buffs  = (p.buffs || []).length
  const tags   = (p.tags  || []).join(', ') || '—'
  document.getElementById('player-panel').innerHTML = `
    <div class="stat"><span class="key">位置</span><span class="val">${pos}</span></div>
    <div class="stat"><span class="key">朝向</span><span class="val">${facing}</span></div>
    <div class="stat"><span class="key">HP</span>
      <div class="bar-wrap">
        <div class="mini-bar"><div class="mini-fill hp-fill" style="width:${hp}%"></div></div>
        <span class="val">${hp}</span>
      </div>
    </div>
    <div class="stat"><span class="key">Energy</span>
      <div class="bar-wrap">
        <div class="mini-bar"><div class="mini-fill en-fill" style="width:${en}%"></div></div>
        <span class="val">${en}</span>
      </div>
    </div>
    <div class="stat"><span class="key">状态</span><span class="val">${state}${label}</span></div>
    <div class="stat"><span class="key">Buffs</span><span class="val">${buffs}</span></div>
    <div class="stat"><span class="key">Tags</span><span class="val" style="font-size:11px">${tags}</span></div>
  `
}
setInterval(() => fetch('/player-status').then(r=>r.json()).then(renderPlayer), 500)
fetch('/player-status').then(r=>r.json()).then(renderPlayer)

// ── log rendering ────────────────────────────────────────────────────────────
const TYPE_MAP = {
  round_start:  { cls: 'round',       tag: '轮次'    },
  thought:      { cls: 'thought',     tag: '思考'    },
  action:       { cls: 'action',      tag: '行动'    },
  observation:  { cls: 'observation', tag: '观察'    },
  finish:       { cls: 'finish',      tag: '完成'    },
  warning:      { cls: 'warning',     tag: '警告'    },
  user_inject:  { cls: 'inject',      tag: '用户指引' },
}

function appendLog(msg) {
  const meta = TYPE_MAP[msg.type] || { cls: 'warning', tag: msg.type }
  let text = ''
  if (msg.type === 'round_start')  text = `第 ${msg.round} 轮`
  else if (msg.type === 'finish')  text = msg.reply
  else                             text = msg.content || ''
  const div = document.createElement('div')
  div.className = `log-entry ${meta.cls}`
  div.innerHTML = `<div class="log-tag">${meta.tag}</div><div class="log-text">${escHtml(text)}</div>`
  logPanel.appendChild(div)
  logPanel.scrollTop = logPanel.scrollHeight
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}

// ── state machine ────────────────────────────────────────────────────────────
function setLoopState(state) {
  loopState = state
  btnRun.disabled   = state !== 'idle'
  btnStop.disabled  = state === 'idle'
  btnPause.disabled = state === 'idle'

  if (state === 'paused') {
    btnPause.textContent = '继续'
    btnPause.classList.add('resume')
    chatSection.classList.add('visible')
    statusDot.className    = 'status-dot paused'
    statusText.textContent = '已暂停'
  } else if (state === 'running') {
    btnPause.textContent = '暂停'
    btnPause.classList.remove('resume')
    chatSection.classList.remove('visible')
    statusDot.className    = 'status-dot running'
    statusText.textContent = '运行中'
  } else {
    btnPause.textContent = '暂停'
    btnPause.classList.remove('resume')
    chatSection.classList.remove('visible')
    statusDot.className    = 'status-dot'
    statusText.textContent = '空闲'
  }
}

// ── controls ─────────────────────────────────────────────────────────────────
function startRun() {
  const task = document.getElementById('task-input').value.trim()
  if (!task) return
  logPanel.innerHTML = ''
  document.getElementById('chat-messages').innerHTML = ''
  setLoopState('running')
  fetch('/run', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({task}) })
    .then(r => r.json())
    .then(d => {
      if (!d.ok) { alert('启动失败：' + d.reason); setLoopState('idle'); return }
      connectWS()
    })
}

function stopRun() {
  fetch('/stop', { method:'POST' })
}

function togglePause() {
  if (loopState === 'running') {
    fetch('/pause', { method:'POST' })
    // UI will update when 'paused' arrives via WebSocket
  } else if (loopState === 'paused') {
    fetch('/resume', { method:'POST' })
    // UI will update when 'resumed' arrives via WebSocket
  }
}

function connectWS() {
  if (ws) { ws.close(); ws = null }
  ws = new WebSocket(`ws://${location.host}/ws`)
  ws.onmessage = e => {
    const msg = JSON.parse(e.data)
    if (msg.type === 'paused') {
      setLoopState('paused')
    } else if (msg.type === 'resumed') {
      setLoopState('running')
    } else if (msg.type === 'loop_end') {
      setTimeout(() => {
        setLoopState('idle')
        fetch('/logging').then(r => r.json()).then(renderLogStatus)
      }, 300)
    } else if (msg.type === 'log_start') {
      renderLogStatus({enabled: true, log_path: msg.path})
    } else {
      appendLog(msg)
    }
  }
  ws.onclose = () => { ws = null }
}

// ── chat ─────────────────────────────────────────────────────────────────────
async function sendChat() {
  const input   = document.getElementById('chat-input')
  const sendBtn = document.getElementById('btn-chat-send')
  const inject  = document.getElementById('inject-cb').checked
  const message = input.value.trim()
  if (!message || sendBtn.disabled) return

  input.value      = ''
  sendBtn.disabled = true
  appendChatBubble('user', message)

  const agentBubble = appendChatBubble('agent', '正在思考…')
  agentBubble.style.opacity = '0.5'

  try {
    const resp = await fetch('/chat', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({ message, inject }),
    })
    const data = await resp.json()
    agentBubble.style.opacity = '1'
    if (data.ok) {
      agentBubble.innerHTML = escHtml(data.reply).replace(/\\n/g, '<br>')
      if (inject) {
        agentBubble.innerHTML += `<div class="chat-inject-tag">✓ 已注入记忆，下一轮生效</div>`
      }
    } else {
      agentBubble.innerHTML = `<span style="color:#f87171">错误：${escHtml(data.reason)}</span>`
    }
  } catch (err) {
    agentBubble.style.opacity = '1'
    agentBubble.innerHTML = `<span style="color:#f87171">网络错误：${escHtml(err.message)}</span>`
  } finally {
    sendBtn.disabled = false
    input.focus()
    document.getElementById('chat-messages').scrollTop = 9999
  }
}

function appendChatBubble(role, text) {
  const messages = document.getElementById('chat-messages')
  const div = document.createElement('div')
  div.className = `chat-bubble chat-${role}`
  div.innerHTML = escHtml(text).replace(/\\n/g, '<br>')
  messages.appendChild(div)
  messages.scrollTop = messages.scrollHeight
  return div
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
