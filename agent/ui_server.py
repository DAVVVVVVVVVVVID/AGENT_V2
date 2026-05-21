"""
Agent UI server — web dashboard for autonomous agent v2.

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
from agent.execute import Execute
from agent.logger import AgentLogger
from agent.loop import run as run_loop
from agent.memory import store
from agent.memory.store import (
    clear_events, clear_recognitions, clear_auxiliary, reset_purpose,
)
from agent.perceive import Perceive
from agent.personality import ocean_to_description
from agent.plan import Planner
from agent.retrieve import Retrieve
from agent.sandbox_client import SandboxClient
from agent.think import Think

app = FastAPI()

_cfg    = AGENT_CONFIG
_client = SandboxClient()

# ── loop state ────────────────────────────────────────────────────────────────
_loop_thread: threading.Thread | None = None
_stop_flag   = threading.Event()
_pause_flag  = threading.Event()
_pause_flag.set()
_msg_queue: queue.Queue[dict] = queue.Queue()
_shared_state: dict = {
    "history":      [],
    "perceive":     None,
    "current_plan": "",
    "plan_batch":   [],
    "plan_index":   0,
}

# ── logging state ─────────────────────────────────────────────────────────────
_logging_enabled              = False
_current_logger: AgentLogger | None = None


def _run_loop_thread() -> None:
    global _current_logger
    cfg = _cfg

    logger: AgentLogger | None = None
    if _logging_enabled:
        logger = AgentLogger("autonomous", cfg)
        _current_logger = logger
        _msg_queue.put({"type": "log_start", "path": logger.path})

    llm = OpenAI(base_url=cfg["llm_base_url"], api_key="ollama")

    perceiver = Perceive(_client, vision_size=cfg["vision_size"])
    retriever = Retrieve(llm, model=cfg["model"])
    planner   = Planner(name=cfg["name"], llm=llm, model=cfg["model"],
                        agent_logger=logger)
    thinker   = Think(
        name=cfg["name"], ocean=cfg["ocean"],
        lifestyle=cfg["lifestyle"],
        common_sense=cfg.get("common_sense", []),
        llm_base_url=cfg["llm_base_url"], model=cfg["model"],
        agent_logger=logger,
    )
    executor  = Execute(_client, entity_id=cfg["entity_id"])

    def emit(msg: dict) -> None:
        if _stop_flag.is_set():
            raise InterruptedError("loop stopped by user")
        _msg_queue.put(msg)
        if logger:
            logger.log_emit(msg)

    try:
        run_loop(
            perceiver=perceiver, retriever=retriever,
            planner=planner, thinker=thinker, executor=executor,
            llm=llm, model=cfg["model"],
            emit=emit,
            pause_flag=_pause_flag,
            stop_flag=_stop_flag,
            shared_state=_shared_state,
        )
    except InterruptedError:
        _msg_queue.put({"type": "warning", "content": "循环已手动停止。"})
    except Exception as e:
        _msg_queue.put({"type": "warning", "content": f"循环异常：{e}"})
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
        "purpose":      store.read_purpose(),
    }


@app.get("/player-status")
def player_status() -> dict:
    try:
        return _client.get_player()
    except Exception as e:
        return {"error": str(e)}


@app.get("/player-buffs")
def player_buffs() -> dict:
    try:
        return _client._get("/admin/player/buffs")
    except Exception as e:
        return {"error": str(e)}


@app.post("/player-force-reset")
def player_force_reset() -> dict:
    try:
        return _client._post("/admin/player/force-reset", {"entity_id": _cfg["entity_id"]})
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/loop-status")
def loop_status() -> dict:
    return {
        "running":      _loop_thread is not None and _loop_thread.is_alive(),
        "current_plan": _shared_state.get("current_plan", ""),
        "plan_batch":   _shared_state.get("plan_batch", []),
        "plan_index":   _shared_state.get("plan_index", 0),
    }


@app.post("/start")
def start_loop() -> dict:
    global _loop_thread
    if _loop_thread and _loop_thread.is_alive():
        return {"ok": False, "reason": "loop already running"}
    _stop_flag.clear()
    _pause_flag.set()
    while not _msg_queue.empty():
        _msg_queue.get_nowait()
    _shared_state.update({"current_plan": "", "plan_batch": [], "plan_index": 0})
    _loop_thread = threading.Thread(target=_run_loop_thread, daemon=True)
    _loop_thread.start()
    return {"ok": True}


@app.post("/stop")
def stop_loop() -> dict:
    _stop_flag.set()
    _pause_flag.set()
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
    history = list(_shared_state.get("history", []))
    plan    = _shared_state.get("current_plan", "")

    history_lines: list[str] = []
    for i, h in enumerate(history, 1):
        history_lines.append(f"第{i}轮：")
        history_lines.append(f"  思考：{h.get('thought', '')}")
        seq = h.get("action_sequence", [])
        if seq:
            history_lines.append("  行动序列：")
            for a in seq:
                s = a.get("status", "")
                detail = str(a.get("result") or a.get("reason") or "")
                history_lines.append(f"    {a['name']} → {s} {detail}")
    history_text = "\n".join(history_lines) if history_lines else "（暂无历史记忆）"

    system = (
        f"你是{cfg['name']}，一个生活在虚拟世界中的角色。\n"
        f"当前正在执行的 Plan：{plan}\n\n"
        "现在 Plan 已暂停，用户正在与你对话。\n"
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
        _shared_state["history"].append({
            "thought": "（用户在此介入提供了指引）",
            "action_sequence": [{
                "name":      "user_inject",
                "arguments": {},
                "status":    "success",
                "result":    {"guidance": message},
            }],
        })
        _msg_queue.put({"type": "user_inject", "content": message})

    if _current_logger:
        _current_logger.log_chat(message, reply, inject)

    return {"ok": True, "reply": reply}


@app.post("/memory/clear")
def memory_clear(body: dict) -> dict:
    """
    清除指定类型的记忆。
    body: {"types": ["events", "recognitions", "auxiliary", "purpose"]}
    "all" 为快捷值，等同于全部四项。
    """
    types = body.get("types", [])
    if "all" in types:
        types = ["events", "recognitions", "auxiliary", "purpose"]

    summary = {}
    if "events" in types:
        summary["events"] = clear_events()
    if "recognitions" in types:
        summary["recognitions"] = clear_recognitions()
    if "auxiliary" in types:
        clear_auxiliary()
        summary["auxiliary"] = "已重置"
    if "purpose" in types:
        reset_purpose("（Purpose 已清空，请重新设定目标）")
        summary["purpose"] = "已重置"

    return {"ok": True, "summary": summary}


@app.get("/memory/purpose")
def get_purpose() -> dict:
    return {"content": store.read_purpose()}


@app.post("/memory/purpose")
def set_purpose(body: dict) -> dict:
    content = body.get("content", "").strip()
    if not content:
        return {"ok": False, "reason": "content is empty"}
    reset_purpose(content)
    return {"ok": True}


@app.get("/memory/files")
def memory_files(type: str = "events") -> dict:
    """返回 events 或 recognitions 的文件列表，含 frontmatter 元数据。"""
    import re
    directory = store.EVENTS_DIR if type == "events" else store.RECOGNITIONS_DIR
    files = []
    for f in sorted(directory.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        meta: dict = {}
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
        files.append({
            "name":        f.name,
            "path":        f"{type}/{f.name}",
            "description": meta.get("Description", ""),
            "time":        meta.get("Time", ""),
            "importance":  meta.get("Importance", ""),
            "keywords":    meta.get("Keywords", ""),
        })
    files.sort(key=lambda x: x["time"], reverse=True)
    return {"type": type, "files": files}


@app.get("/memory/file")
def memory_file(path: str) -> dict:
    """返回指定记忆文件全文。path 为相对于 memory/ 的路径。"""
    fp = store.MEMORY_DIR / path
    if not fp.exists() or not fp.is_relative_to(store.MEMORY_DIR):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="file not found")
    return {"path": path, "content": fp.read_text(encoding="utf-8")}


@app.get("/memory/keywords-data")
def memory_keywords_data() -> dict:
    """返回 keywords.md 解析后的数据。"""
    import re
    rows = []
    if store.KEYWORDS_FILE.exists():
        for line in store.KEYWORDS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^(.+?):\s*(\d+),\s*\[(.*)\]\s*$", line)
            if m:
                files = [f.strip() for f in m.group(3).split(",") if f.strip()]
                rows.append({
                    "keyword": m.group(1).strip(),
                    "count":   int(m.group(2)),
                    "files":   files,
                })
    rows.sort(key=lambda x: x["count"], reverse=True)
    return {"rows": rows}


@app.get("/memory/index-data")
def memory_index_data() -> dict:
    """返回 Memory.md 解析后的条目列表。"""
    import re
    entries = []
    if store.MEMORY_INDEX.exists():
        pattern = re.compile(r"- \[(.+?)\]\((.+?)\) — (.+?) \| (.+?) \| imp=(\d+)")
        for line in store.MEMORY_INDEX.read_text(encoding="utf-8").splitlines():
            m = pattern.match(line.strip())
            if m:
                entries.append({
                    "name":        m.group(1),
                    "path":        m.group(2),
                    "description": m.group(3),
                    "time":        m.group(4),
                    "importance":  int(m.group(5)),
                })
    entries.sort(key=lambda x: x["time"], reverse=True)
    return {"entries": entries}


@app.get("/memory-viewer")
def memory_viewer() -> HTMLResponse:
    return HTMLResponse(_MEMORY_HTML)


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

_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>Agent v2 Control Panel</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; height: 100vh; display: flex; flex-direction: column; }

  header { padding: 12px 20px; background: #1a1d27; border-bottom: 1px solid #2d3148; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 16px; font-weight: 600; color: #a78bfa; }
  #status-badge { font-size: 11px; padding: 2px 10px; border-radius: 10px; background: #1e2235; color: #6b7280; }
  #status-badge.running { background: #052e16; color: #4ade80; }
  #status-badge.paused  { background: #451a03; color: #fbbf24; }
  .log-toggle-wrap { margin-left: auto; display: flex; align-items: center; gap: 10px; }
  .log-toggle-label { font-size: 12px; color: #6b7280; white-space: nowrap; }
  .toggle { position: relative; display: inline-block; width: 36px; height: 20px; flex-shrink: 0; }
  .toggle input { opacity: 0; width: 0; height: 0; }
  .toggle-slider { position: absolute; cursor: pointer; inset: 0; background: #374151; border-radius: 20px; transition: .2s; }
  .toggle-slider:before { position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px; background: #fff; border-radius: 50%; transition: .2s; }
  .toggle input:checked + .toggle-slider { background: #6d28d9; }
  .toggle input:checked + .toggle-slider:before { transform: translateX(16px); }
  #log-path-display { font-size: 11px; color: #4b5563; font-family: monospace; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #log-path-display.active { color: #34d399; }

  .main { flex: 1; display: grid; grid-template-columns: 260px 220px 1fr; gap: 0; overflow: hidden; }
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
  .purpose-box { background: #1a1d27; border: 1px solid #2d3148; border-radius: 6px; padding: 8px 10px; font-size: 12px; color: #c4b5fd; line-height: 1.6; margin-bottom: 14px; }

  /* middle panel: player + plan */
  .mid-section { border-bottom: 1px solid #1e2235; flex-shrink: 0; }
  .mid-section .panel-title { border-bottom: 1px solid #1e2235; }
  .mid-body { padding: 10px 14px; font-size: 12px; overflow-y: auto; }
  .stat { display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-bottom: 1px solid #1a1d27; }
  .stat:last-child { border-bottom: none; }
  .stat .key { font-size: 12px; color: #6b7280; }
  .stat .val { font-size: 12px; color: #e2e8f0; font-family: monospace; }
  .bar-wrap { display: flex; align-items: center; gap: 6px; }
  .mini-bar { width: 60px; height: 5px; background: #1e2235; border-radius: 3px; overflow: hidden; }
  .mini-fill { height: 100%; border-radius: 3px; }
  .hp-fill { background: #ef4444; }
  .en-fill { background: #f59e0b; }

  /* plan batch */
  .plan-item { display: flex; gap: 8px; align-items: flex-start; padding: 5px 0; border-bottom: 1px solid #1a1d27; font-size: 12px; line-height: 1.5; }
  .plan-item:last-child { border-bottom: none; }
  .plan-icon { flex-shrink: 0; font-size: 13px; margin-top: 1px; }
  .plan-item.done .plan-text  { color: #4b5563; text-decoration: line-through; }
  .plan-item.active .plan-text { color: #a78bfa; font-weight: 600; }
  .plan-item.todo .plan-text  { color: #9ca3af; }

  /* loop log */
  .log-entry { margin-bottom: 10px; border-left: 3px solid #2d3148; padding-left: 10px; }
  .log-entry.outer    { border-color: #7c3aed; }
  .log-entry.plan-b   { border-color: #0e7490; }
  .log-entry.plan-s   { border-color: #0891b2; }
  .log-entry.round    { border-color: #4b5563; }
  .log-entry.thought  { border-color: #6d28d9; }
  .log-entry.action-s { border-color: #0284c7; }
  .log-entry.result   { border-color: #059669; }
  .log-entry.finish   { border-color: #d97706; }
  .log-entry.warning  { border-color: #dc2626; }
  .log-entry.inject   { border-color: #0891b2; }
  .log-tag  { font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 3px; }
  .log-entry.outer    .log-tag { color: #c4b5fd; }
  .log-entry.plan-b   .log-tag { color: #22d3ee; }
  .log-entry.plan-s   .log-tag { color: #38bdf8; }
  .log-entry.round    .log-tag { color: #9ca3af; }
  .log-entry.thought  .log-tag { color: #a78bfa; }
  .log-entry.action-s .log-tag { color: #38bdf8; }
  .log-entry.result   .log-tag { color: #34d399; }
  .log-entry.finish   .log-tag { color: #fbbf24; }
  .log-entry.warning  .log-tag { color: #f87171; }
  .log-entry.inject   .log-tag { color: #22d3ee; }
  .log-text { font-size: 12px; color: #d1d5db; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }

  /* chat */
  #chat-section { display: none; flex-direction: column; flex: 0 0 280px; overflow: hidden; border-top: 2px solid #f59e0b55; }
  #chat-section.visible { display: flex; }
  .chat-header { padding: 8px 14px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; background: #13161f; border-bottom: 1px solid #1e2235; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; color: #f59e0b; }
  #chat-messages { flex: 1; height: 0; overflow-y: auto; padding: 10px 14px; display: flex; flex-direction: column; gap: 8px; }
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

  /* footer */
  footer { padding: 12px 16px; background: #1a1d27; border-top: 1px solid #2d3148; display: flex; gap: 10px; align-items: center; }
  footer button { padding: 8px 22px; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; }
  #btn-start { background: #6d28d9; color: #fff; }
  #btn-start:hover    { background: #7c3aed; }
  #btn-start:disabled { background: #374151; color: #6b7280; cursor: not-allowed; }
  #btn-pause { background: #78350f; color: #fcd34d; }
  #btn-pause:hover    { background: #92400e; }
  #btn-pause.resume   { background: #064e3b; color: #6ee7b7; }
  #btn-pause.resume:hover { background: #065f46; }
  #btn-pause:disabled { background: #1f2937; color: #4b5563; cursor: not-allowed; }
  #btn-stop  { background: #7f1d1d; color: #fca5a5; }
  #btn-stop:hover     { background: #991b1b; }
  #btn-stop:disabled  { background: #1f2937; color: #4b5563; cursor: not-allowed; }
  #btn-clear-mem { background: #1c1917; color: #78716c; border: 1px solid #292524; }
  #btn-clear-mem:hover { background: #292524; color: #a8a29e; }
  .footer-info { font-size: 12px; color: #4b5563; margin-left: auto; }

  /* 清除记忆弹窗 */
  .modal-overlay { display: none; position: fixed; inset: 0; background: #00000088; z-index: 100; align-items: center; justify-content: center; }
  .modal-overlay.visible { display: flex; }
  .modal-box { background: #1a1d27; border: 1px solid #2d3148; border-radius: 10px; padding: 24px; width: 340px; }
  .modal-title { font-size: 15px; font-weight: 600; color: #e2e8f0; margin-bottom: 6px; }
  .modal-warn  { font-size: 12px; color: #f87171; margin-bottom: 16px; }
  .modal-checks { display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px; }
  .modal-check-row { display: flex; align-items: center; gap: 10px; font-size: 13px; cursor: pointer; }
  .modal-check-row input { accent-color: #6d28d9; width: 15px; height: 15px; cursor: pointer; }
  .modal-check-row .check-label { color: #d1d5db; }
  .modal-check-row .check-desc  { font-size: 11px; color: #4b5563; margin-left: auto; }
  .modal-divider { border: none; border-top: 1px solid #2d3148; margin: 4px 0 14px; }
  .modal-actions { display: flex; gap: 10px; justify-content: flex-end; }
  .modal-actions button { padding: 7px 18px; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; }
  #modal-cancel  { background: #1f2937; color: #9ca3af; }
  #modal-cancel:hover { background: #374151; }
  #modal-confirm { background: #991b1b; color: #fca5a5; }
  #modal-confirm:hover { background: #7f1d1d; }
  #modal-confirm:disabled { background: #374151; color: #6b7280; cursor: not-allowed; }
</style>
</head>
<body>

<header>
  <h1>Agent v2</h1>
  <span id="status-badge">空闲</span>
  <a href="/memory-viewer" target="_blank" style="font-size:12px;color:#6b7280;text-decoration:none;padding:3px 10px;border:1px solid #2d3148;border-radius:6px;">记忆查看器 ↗</a>
  <div class="log-toggle-wrap">
    <span class="log-toggle-label">记录日志</span>
    <label class="toggle">
      <input type="checkbox" id="log-toggle" onchange="setLogging(this.checked)">
      <span class="toggle-slider"></span>
    </label>
    <span id="log-path-display"></span>
  </div>
</header>

<div class="main">

  <!-- 左：Agent 参数 -->
  <div class="panel">
    <div class="panel-title">Agent 参数</div>
    <div class="panel-body" id="agent-panel">加载中…</div>
  </div>

  <!-- 中：Player 状态 + Plan 状态 -->
  <div class="panel" style="display:flex;flex-direction:column;">
    <div class="mid-section" style="flex:0 0 auto;">
      <div class="panel-title">Player 状态</div>
      <div class="mid-body" id="player-panel">加载中…</div>
    </div>
    <div style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <div class="panel-title">Plan 状态</div>
      <div class="mid-body" id="plan-panel" style="flex:1;overflow-y:auto;">
        <div style="color:#4b5563;font-size:12px;">等待 agent 启动…</div>
      </div>
    </div>
  </div>

  <!-- 右：Loop 输出 + 对话 -->
  <div class="panel">
    <div class="panel-title">Loop 输出</div>
    <div class="panel-body" id="log-panel"></div>

    <div id="chat-section">
      <div class="chat-header">
        <span>对话</span>
        <span style="font-size:10px;background:#78350f44;padding:2px 7px;border-radius:10px;">⏸ 已暂停</span>
      </div>
      <div id="chat-messages"></div>
      <div class="chat-input-row">
        <input type="text" id="chat-input" placeholder="输入问题或指令…"
               onkeydown="if(event.key==='Enter'&&!event.shiftKey)sendChat()" />
        <label class="inject-label" title="将消息注入 Agent 记忆">
          <input type="checkbox" id="inject-cb"> 注入
        </label>
        <button id="btn-chat-send" onclick="sendChat()">发送</button>
      </div>
    </div>
  </div>

</div>

<!-- 清除记忆弹窗 -->
<div class="modal-overlay" id="clear-modal">
  <div class="modal-box">
    <div class="modal-title">清除记忆</div>
    <div class="modal-warn">⚠ 此操作不可撤销，请谨慎选择</div>
    <div class="modal-checks">
      <label class="modal-check-row">
        <input type="checkbox" id="chk-all" onchange="toggleAll(this)">
        <span class="check-label" style="color:#e2e8f0;font-weight:600;">全部</span>
      </label>
      <hr class="modal-divider">
      <label class="modal-check-row">
        <input type="checkbox" class="chk-item" value="events">
        <span class="check-label">Events 记忆</span>
        <span class="check-desc">events/*.md</span>
      </label>
      <label class="modal-check-row">
        <input type="checkbox" class="chk-item" value="recognitions">
        <span class="check-label">Recognition 记忆</span>
        <span class="check-desc">recognitions/*.md</span>
      </label>
      <label class="modal-check-row">
        <input type="checkbox" class="chk-item" value="auxiliary">
        <span class="check-label">辅助索引</span>
        <span class="check-desc">Memory.md + keywords.md</span>
      </label>
      <label class="modal-check-row">
        <input type="checkbox" class="chk-item" value="purpose">
        <span class="check-label">Purpose</span>
        <span class="check-desc">purpose.md</span>
      </label>
    </div>
    <div class="modal-actions">
      <button id="modal-cancel"  onclick="closeModal()">取消</button>
      <button id="modal-confirm" onclick="confirmClear()" disabled>确认清除</button>
    </div>
  </div>
</div>

<footer>
  <button id="btn-start" onclick="startLoop()">启动</button>
  <button id="btn-pause" disabled onclick="togglePause()">暂停</button>
  <button id="btn-stop"  disabled onclick="stopLoop()">停止</button>
  <button id="btn-clear-mem" onclick="openModal()">清除记忆</button>
  <span class="footer-info" id="footer-info"></span>
</footer>

<script>
const logPanel    = document.getElementById('log-panel')
const planPanel   = document.getElementById('plan-panel')
const statusBadge = document.getElementById('status-badge')
const btnStart    = document.getElementById('btn-start')
const btnPause    = document.getElementById('btn-pause')
const btnStop     = document.getElementById('btn-stop')
const footerInfo  = document.getElementById('footer-info')
const chatSection = document.getElementById('chat-section')
let ws = null
let loopState = 'idle'

// ── logging ──────────────────────────────────────────────────────────────────
fetch('/logging').then(r=>r.json()).then(renderLogStatus)
function setLogging(en) {
  fetch('/logging',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:en})})
    .then(r=>r.json()).then(renderLogStatus)
}
function renderLogStatus(d) {
  document.getElementById('log-toggle').checked = d.enabled
  const el = document.getElementById('log-path-display')
  if (d.log_path) {
    el.textContent = d.log_path.split('/').pop()
    el.className   = 'active'; el.title = d.log_path
  } else {
    el.textContent = d.enabled ? '下次启动时生效' : ''
    el.className   = ''; el.title = ''
  }
}

// ── agent config ─────────────────────────────────────────────────────────────
fetch('/agent-config').then(r=>r.json()).then(cfg => {
  const ocean = cfg.ocean
  const bars  = ['O','C','E','A','N'].map(k=>`
    <div class="ocean-bar">
      <span>${k}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${ocean[k]}%"></div></div>
      <span>${ocean[k]}</span>
    </div>`).join('')
  const lifestyle = cfg.lifestyle.map(s=>`<div class="list-item">· ${s}</div>`).join('')
  const sense     = (cfg.common_sense||[]).map(s=>`<div class="list-item">· ${s}</div>`).join('')
  document.getElementById('agent-panel').innerHTML = `
    <div class="field"><label>名称</label><div class="val">${cfg.name}</div></div>
    <div class="field"><label>实体 ID</label><div class="val mono">${cfg.entity_id}</div></div>
    <div class="field"><label>模型</label><div class="val mono">${cfg.model}</div></div>
    <div class="field"><label>视野范围</label><div class="val">${cfg.vision_size}×${cfg.vision_size}</div></div>
    <div class="field"><label>Purpose</label><div class="purpose-box">${esc(cfg.purpose)}</div></div>
    <div class="field"><label>OCEAN</label>${bars}</div>
    <div class="field"><label>生活方式</label>${lifestyle}</div>
    ${sense?`<div class="field"><label>常识</label>${sense}</div>`:''}
  `
})

// ── player status ────────────────────────────────────────────────────────────
function renderPlayer(p) {
  if (p.error) { document.getElementById('player-panel').innerHTML=`<span style="color:#f87171">${esc(p.error)}</span>`; return }
  const pos   = p.position?`(${p.position.x}, ${p.position.y})`:'-'
  const fmap  = {up:'上',down:'下',left:'左',right:'右'}
  const facing= fmap[p.facing]||p.facing||'-'
  const hp    = p.hp??0; const en = p.energy??0
  const label = p.stateLabel?`<br><span style="color:#fbbf24;font-size:11px">${esc(p.stateLabel)}</span>`:''

  const buffs = p.buffs || []
  const noMove     = buffs.some(b=>b.key==='no_move')
  const noInteract = buffs.some(b=>b.key==='no_interact')
  const noUse      = buffs.some(b=>b.key==='no_use')
  const blocked    = noMove || noInteract || noUse

  const buffHtml = buffs.length === 0
    ? `<span style="color:#4b5563;font-size:11px">无</span>`
    : buffs.map(b => {
        const rem = b.remaining != null ? `${Math.ceil(b.remaining/1000)}s` : '∞'
        const danger = ['no_move','no_interact','no_use'].includes(b.key)
        const color  = danger ? '#f87171' : '#34d399'
        return `<span style="display:inline-block;background:#1e2235;border:1px solid ${danger?'#7f1d1d':'#064e3b'};color:${color};font-size:10px;padding:1px 5px;border-radius:4px;margin:1px;font-family:monospace">${esc(b.key)} ${rem}</span>`
      }).join('')

  document.getElementById('player-panel').innerHTML = `
    <div class="stat"><span class="key">位置</span><span class="val">${pos}</span></div>
    <div class="stat"><span class="key">朝向</span><span class="val">${facing}</span></div>
    <div class="stat"><span class="key">HP</span><div class="bar-wrap">
      <div class="mini-bar"><div class="mini-fill hp-fill" style="width:${hp}%"></div></div>
      <span class="val">${hp}</span></div></div>
    <div class="stat"><span class="key">Energy</span><div class="bar-wrap">
      <div class="mini-bar"><div class="mini-fill en-fill" style="width:${en}%"></div></div>
      <span class="val">${en}</span></div></div>
    <div class="stat"><span class="key">状态</span><span class="val">${esc(p.state||'-')}${label}</span></div>
    <div class="stat" style="align-items:flex-start"><span class="key" style="padding-top:3px">Buffs</span><div style="flex:1">${buffHtml}</div></div>
    ${blocked ? `<div style="margin-top:8px"><button onclick="forceResetPlayer()" style="width:100%;padding:5px 0;background:#7f1d1d;color:#fca5a5;border:none;border-radius:5px;font-size:12px;font-weight:600;cursor:pointer">⚠ 强制离开 / 清除 Buff</button></div>` : ''}
  `
}
async function forceResetPlayer() {
  const resp = await fetch('/player-force-reset', {method:'POST'})
  const d = await resp.json()
  const div = document.createElement('div')
  div.className = 'log-entry warning'
  const msg = d.ok
    ? `强制重置完成：离开对象 ${d.left_object||'无'}，清除 ${d.cleared_buffs} 个 buff`
    : `强制重置失败：${esc(d.error||'unknown')}`
  div.innerHTML = `<div class="log-tag">强制重置</div><div class="log-text">${esc(msg)}</div>`
  document.getElementById('log-panel').appendChild(div)
}
setInterval(()=>fetch('/player-status').then(r=>r.json()).then(renderPlayer), 500)
fetch('/player-status').then(r=>r.json()).then(renderPlayer)

// ── plan status ──────────────────────────────────────────────────────────────
let _planBatch = []; let _planIndex = 0
function renderPlan(batch, idx) {
  _planBatch = batch; _planIndex = idx
  if (!batch || batch.length === 0) {
    planPanel.innerHTML = '<div style="color:#4b5563;font-size:12px;">等待规划…</div>'
    return
  }
  planPanel.innerHTML = batch.map((p, i) => {
    const n = i + 1
    const done   = n < idx
    const active = n === idx
    const icon   = done ? '✓' : active ? '▶' : '○'
    const cls    = done ? 'done' : active ? 'active' : 'todo'
    return `<div class="plan-item ${cls}">
      <span class="plan-icon">${icon}</span>
      <span class="plan-text">${n}. ${esc(p)}</span>
    </div>`
  }).join('')
  footerInfo.textContent = idx > 0 ? `Plan ${idx}/${batch.length}` : ''
}

// ── log rendering ────────────────────────────────────────────────────────────
function appendLog(msg) {
  const div = document.createElement('div')
  let cls='warning', tag=msg.type, text=''

  if (msg.type === 'outer_start') {
    cls='outer'; tag='规划阶段'; text='正在生成新的 Plan Batch…'
  } else if (msg.type === 'plan_batch') {
    cls='plan-b'; tag='Plan Batch'
    text = msg.plans.map((p,i)=>`${i+1}. ${p}`).join('\n')
    renderPlan(msg.plans, 1)
  } else if (msg.type === 'plan_start') {
    cls='plan-s'; tag=`Plan ${msg.plan_index}/${msg.total}`
    text = msg.plan
    renderPlan(_planBatch, msg.plan_index)
  } else if (msg.type === 'round_start') {
    cls='round'; tag='轮次'; text=`第 ${msg.round} 轮`
  } else if (msg.type === 'thought') {
    cls='thought'; tag='思考'; text=msg.content
  } else if (msg.type === 'action_sequence') {
    cls='action-s'; tag='行动序列'
    text = msg.actions.map(a=>{
      const args = Object.entries(a.arguments||{}).map(([k,v])=>`${k}=${JSON.stringify(v)}`).join(', ')
      return `→ ${a.name}(${args})`
    }).join('\n')
  } else if (msg.type === 'action_result') {
    cls='result'; tag='执行结果'
    text = msg.snapshot.map(a=>{
      if (a.status==='success') return `✓ ${a.name}: ${JSON.stringify(a.result)}`
      if (a.status==='failed')  return `✗ ${a.name}: ${a.reason}`
      return `… ${a.name}: 未执行`
    }).join('\n')
  } else if (msg.type === 'plan_finish') {
    cls='finish'; tag='Plan 完成'; text=msg.reply
  } else if (msg.type === 'warning') {
    cls='warning'; tag='警告'; text=msg.content
  } else if (msg.type === 'user_inject') {
    cls='inject'; tag='用户指引'; text=msg.content
  }

  div.className = `log-entry ${cls}`
  div.innerHTML = `<div class="log-tag">${tag}</div><div class="log-text">${esc(text)}</div>`
  logPanel.appendChild(div)
  logPanel.scrollTop = logPanel.scrollHeight
}

// ── state machine ────────────────────────────────────────────────────────────
function setLoopState(state) {
  loopState = state
  btnStart.disabled = state !== 'idle'
  btnStop.disabled  = state === 'idle'
  btnPause.disabled = state === 'idle'
  if (state === 'paused') {
    statusBadge.textContent='已暂停'; statusBadge.className='paused'
    btnPause.textContent='继续'; btnPause.classList.add('resume')
    chatSection.classList.add('visible')
  } else if (state === 'running') {
    statusBadge.textContent='运行中'; statusBadge.className='running'
    btnPause.textContent='暂停'; btnPause.classList.remove('resume')
    chatSection.classList.remove('visible')
  } else {
    statusBadge.textContent='空闲'; statusBadge.className=''
    btnPause.textContent='暂停'; btnPause.classList.remove('resume')
    chatSection.classList.remove('visible')
    footerInfo.textContent=''
  }
}

// ── controls ─────────────────────────────────────────────────────────────────
function startLoop() {
  logPanel.innerHTML=''
  document.getElementById('chat-messages').innerHTML=''
  planPanel.innerHTML='<div style="color:#4b5563;font-size:12px;">等待规划…</div>'
  setLoopState('running')
  fetch('/start',{method:'POST'}).then(r=>r.json()).then(d=>{
    if (!d.ok) { alert('启动失败：'+d.reason); setLoopState('idle'); return }
    connectWS()
  })
}
function stopLoop() { fetch('/stop',{method:'POST'}) }
function togglePause() {
  if (loopState==='running')      fetch('/pause', {method:'POST'})
  else if (loopState==='paused')  fetch('/resume',{method:'POST'})
}
function connectWS() {
  if (ws) { ws.close(); ws=null }
  ws = new WebSocket(`ws://${location.host}/ws`)
  ws.onmessage = e => {
    const msg = JSON.parse(e.data)
    if      (msg.type==='paused')   setLoopState('paused')
    else if (msg.type==='resumed')  setLoopState('running')
    else if (msg.type==='loop_end') { setTimeout(()=>{ setLoopState('idle'); fetch('/logging').then(r=>r.json()).then(renderLogStatus) },300) }
    else if (msg.type==='log_start') renderLogStatus({enabled:true,log_path:msg.path})
    else appendLog(msg)
  }
  ws.onclose = () => { ws=null }
}

// ── chat ─────────────────────────────────────────────────────────────────────
async function sendChat() {
  const input   = document.getElementById('chat-input')
  const sendBtn = document.getElementById('btn-chat-send')
  const inject  = document.getElementById('inject-cb').checked
  const message = input.value.trim()
  if (!message||sendBtn.disabled) return
  input.value=''; sendBtn.disabled=true
  appendChatBubble('user', message)
  const ab = appendChatBubble('agent', '正在思考…'); ab.style.opacity='0.5'
  try {
    const resp = await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,inject})})
    const data = await resp.json()
    ab.style.opacity='1'
    if (data.ok) {
      ab.innerHTML = esc(data.reply).replace(/\n/g,'<br>')
      if (inject) ab.innerHTML += `<div class="chat-inject-tag">✓ 已注入记忆，下一轮生效</div>`
    } else {
      ab.innerHTML = `<span style="color:#f87171">错误：${esc(data.reason)}</span>`
    }
  } catch(err) {
    ab.style.opacity='1'; ab.innerHTML=`<span style="color:#f87171">网络错误：${esc(err.message)}</span>`
  } finally {
    sendBtn.disabled=false; input.focus()
    document.getElementById('chat-messages').scrollTop=9999
  }
}
function appendChatBubble(role, text) {
  const msgs = document.getElementById('chat-messages')
  const div  = document.createElement('div')
  div.className=`chat-bubble chat-${role}`
  div.innerHTML=esc(text).replace(/\n/g,'<br>')
  msgs.appendChild(div); msgs.scrollTop=msgs.scrollHeight
  return div
}
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}

// ── 清除记忆弹窗 ─────────────────────────────────────────────────────────────
function openModal() {
  document.getElementById('clear-modal').classList.add('visible')
}
function closeModal() {
  document.getElementById('clear-modal').classList.remove('visible')
  // 重置选择
  document.querySelectorAll('.chk-item').forEach(c => c.checked = false)
  document.getElementById('chk-all').checked = false
  document.getElementById('modal-confirm').disabled = true
}
function toggleAll(el) {
  document.querySelectorAll('.chk-item').forEach(c => { c.checked = el.checked })
  document.getElementById('modal-confirm').disabled = !el.checked
}
// 点选子项时同步全选框和确认按钮状态
document.querySelectorAll('.chk-item').forEach(c => {
  c.addEventListener('change', () => {
    const items = document.querySelectorAll('.chk-item')
    const checked = [...items].filter(i => i.checked)
    document.getElementById('chk-all').checked = checked.length === items.length
    document.getElementById('modal-confirm').disabled = checked.length === 0
  })
})
// 点击遮罩关闭
document.getElementById('clear-modal').addEventListener('click', e => {
  if (e.target === document.getElementById('clear-modal')) closeModal()
})
async function confirmClear() {
  const types = [...document.querySelectorAll('.chk-item:checked')].map(c => c.value)
  if (types.length === 0) return
  document.getElementById('modal-confirm').disabled = true
  try {
    const resp = await fetch('/memory/clear', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({types}),
    })
    const data = await resp.json()
    if (data.ok) {
      const parts = Object.entries(data.summary).map(([k,v]) => `${k}: ${v}`)
      closeModal()
      const div = document.createElement('div')
      div.className = 'log-entry warning'
      div.innerHTML = `<div class="log-tag">记忆清除</div><div class="log-text">已清除：${esc(parts.join('，'))}</div>`
      logPanel.appendChild(div)
      logPanel.scrollTop = logPanel.scrollHeight
    }
  } catch(err) {
    alert('清除失败：' + err.message)
    document.getElementById('modal-confirm').disabled = false
  }
}
</script>
</body>
</html>"""


_MEMORY_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>记忆查看器 — Agent v2</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; height: 100vh; display: flex; flex-direction: column; }

  header { padding: 10px 20px; background: #1a1d27; border-bottom: 1px solid #2d3148; display: flex; align-items: center; gap: 14px; }
  header h1 { font-size: 15px; font-weight: 600; color: #a78bfa; }
  .back-link { font-size: 12px; color: #6b7280; text-decoration: none; padding: 3px 10px; border: 1px solid #2d3148; border-radius: 6px; }
  .back-link:hover { color: #e2e8f0; border-color: #4b5563; }
  .header-refresh { margin-left: auto; font-size: 12px; color: #6b7280; cursor: pointer; padding: 3px 10px; border: 1px solid #2d3148; border-radius: 6px; background: none; }
  .header-refresh:hover { color: #e2e8f0; }

  .layout { flex: 1; display: flex; overflow: hidden; }

  /* 左侧导航 */
  .sidebar { width: 220px; flex-shrink: 0; background: #13161f; border-right: 1px solid #1e2235; display: flex; flex-direction: column; overflow-y: auto; }
  .sidebar::-webkit-scrollbar { width: 3px; }
  .sidebar::-webkit-scrollbar-thumb { background: #2d3148; }
  .nav-section { padding: 14px 14px 6px; font-size: 10px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: #4b5563; }
  .nav-item { display: flex; align-items: center; gap: 8px; padding: 7px 14px; font-size: 13px; color: #9ca3af; cursor: pointer; border-left: 2px solid transparent; user-select: none; }
  .nav-item:hover { background: #1a1d27; color: #e2e8f0; }
  .nav-item.active { background: #1a1d27; color: #a78bfa; border-left-color: #6d28d9; }
  .nav-item .nav-icon { font-size: 14px; width: 18px; text-align: center; flex-shrink: 0; }
  .nav-item .nav-count { margin-left: auto; font-size: 10px; background: #1e2235; padding: 1px 6px; border-radius: 8px; color: #6b7280; }
  .nav-divider { border: none; border-top: 1px solid #1e2235; margin: 6px 0; }

  /* 右侧内容 */
  .content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .content-header { padding: 12px 20px; background: #13161f; border-bottom: 1px solid #1e2235; display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
  .content-title { font-size: 14px; font-weight: 600; color: #e2e8f0; }
  .content-subtitle { font-size: 12px; color: #4b5563; }
  .content-body { flex: 1; overflow-y: auto; padding: 20px; }
  .content-body::-webkit-scrollbar { width: 4px; }
  .content-body::-webkit-scrollbar-thumb { background: #2d3148; border-radius: 2px; }

  /* Purpose */
  .purpose-textarea { width: 100%; min-height: 120px; background: #1a1d27; border: 1px solid #2d3148; border-radius: 8px; padding: 12px; color: #c4b5fd; font-size: 14px; line-height: 1.7; resize: vertical; outline: none; font-family: inherit; }
  .purpose-textarea:focus { border-color: #6d28d9; }
  .save-btn { margin-top: 10px; padding: 7px 20px; background: #6d28d9; color: #fff; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; }
  .save-btn:hover { background: #7c3aed; }
  .save-msg { font-size: 12px; color: #34d399; margin-left: 10px; }

  /* 文件列表 */
  .file-list { display: flex; flex-direction: column; gap: 6px; }
  .file-card { background: #1a1d27; border: 1px solid #1e2235; border-radius: 8px; padding: 10px 14px; cursor: pointer; transition: border-color .15s; display: flex; align-items: flex-start; gap: 12px; }
  .file-card:hover { border-color: #6d28d9; }
  .file-card.selected { border-color: #6d28d9; background: #1e1533; }
  .file-card-left { flex: 1; min-width: 0; }
  .file-name { font-size: 12px; font-family: monospace; color: #93c5fd; margin-bottom: 3px; }
  .file-desc { font-size: 12px; color: #d1d5db; line-height: 1.5; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .file-meta { font-size: 11px; color: #4b5563; margin-top: 4px; }
  .imp-badge { display: inline-block; padding: 1px 7px; border-radius: 8px; font-size: 11px; font-weight: 600; flex-shrink: 0; }
  .imp-high   { background: #7f1d1d33; color: #f87171; }
  .imp-mid    { background: #78350f33; color: #fbbf24; }
  .imp-low    { background: #1e293b;   color: #64748b; }

  /* 文件内容查看 */
  .file-viewer { display: flex; gap: 0; height: 100%; overflow: hidden; }
  .file-viewer-list { width: 300px; flex-shrink: 0; border-right: 1px solid #1e2235; overflow-y: auto; padding: 4px; }
  .file-viewer-list::-webkit-scrollbar { width: 3px; }
  .file-viewer-list::-webkit-scrollbar-thumb { background: #2d3148; }
  .file-viewer-detail { flex: 1; overflow-y: auto; padding: 16px 20px; }
  .file-viewer-detail::-webkit-scrollbar { width: 4px; }
  .file-viewer-detail::-webkit-scrollbar-thumb { background: #2d3148; border-radius: 2px; }

  /* 记忆内容渲染 */
  .fm-grid { display: grid; grid-template-columns: 100px 1fr; gap: 6px 12px; background: #13161f; border: 1px solid #1e2235; border-radius: 8px; padding: 12px 14px; margin-bottom: 16px; }
  .fm-key { font-size: 11px; color: #6b7280; text-align: right; padding-top: 2px; }
  .fm-val { font-size: 12px; color: #d1d5db; line-height: 1.5; }
  .fm-val.kw { color: #a78bfa; }
  .fm-val.imp { font-weight: 700; }
  .body-section { margin-bottom: 14px; }
  .body-section h2 { font-size: 13px; font-weight: 700; color: #38bdf8; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #1e2235; }
  .body-section p  { font-size: 13px; color: #d1d5db; line-height: 1.7; white-space: pre-wrap; }
  .empty-hint { color: #4b5563; font-size: 13px; padding: 20px 0; }

  /* Memory Index 表格 */
  .mem-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .mem-table th { text-align: left; padding: 8px 10px; background: #13161f; color: #6b7280; font-weight: 600; font-size: 11px; letter-spacing: .05em; border-bottom: 1px solid #1e2235; position: sticky; top: 0; }
  .mem-table td { padding: 8px 10px; border-bottom: 1px solid #13161f; color: #d1d5db; vertical-align: top; }
  .mem-table tr:hover td { background: #1a1d27; }
  .mem-table .td-name { font-family: monospace; color: #93c5fd; white-space: nowrap; }
  .mem-table .td-imp  { text-align: center; font-weight: 700; }
  .mem-table .td-time { color: #4b5563; white-space: nowrap; font-size: 11px; }

  /* Keywords 表格 */
  .kw-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .kw-table th { text-align: left; padding: 8px 10px; background: #13161f; color: #6b7280; font-weight: 600; font-size: 11px; border-bottom: 1px solid #1e2235; position: sticky; top: 0; }
  .kw-table td { padding: 8px 10px; border-bottom: 1px solid #13161f; vertical-align: top; }
  .kw-table tr:hover td { background: #1a1d27; }
  .kw-word { color: #a78bfa; font-weight: 600; }
  .kw-count { text-align: center; color: #fbbf24; font-weight: 700; }
  .kw-files { color: #4b5563; font-size: 11px; line-height: 1.6; }
  .kw-file-chip { display: inline-block; background: #1e2235; padding: 1px 6px; border-radius: 4px; margin: 1px 2px; font-family: monospace; cursor: pointer; }
  .kw-file-chip:hover { background: #2d3148; color: #93c5fd; }
</style>
</head>
<body>

<header>
  <h1>记忆查看器</h1>
  <a href="/" class="back-link">← 返回控制台</a>
  <button class="header-refresh" onclick="refreshCurrent()">刷新</button>
</header>

<div class="layout">

  <!-- 左侧导航 -->
  <div class="sidebar">
    <div class="nav-section">特殊文件</div>
    <div class="nav-item" onclick="showSection('purpose')" id="nav-purpose">
      <span class="nav-icon">🎯</span> Purpose
    </div>
    <div class="nav-item" onclick="showSection('index')" id="nav-index">
      <span class="nav-icon">📋</span> Memory Index
    </div>
    <div class="nav-item" onclick="showSection('keywords')" id="nav-keywords">
      <span class="nav-icon">🔑</span> Keywords
    </div>
    <hr class="nav-divider">
    <div class="nav-section">记忆文件</div>
    <div class="nav-item" onclick="showSection('events')" id="nav-events">
      <span class="nav-icon">📅</span> Events
      <span class="nav-count" id="cnt-events">-</span>
    </div>
    <div class="nav-item" onclick="showSection('recognitions')" id="nav-recognitions">
      <span class="nav-icon">💭</span> Recognitions
      <span class="nav-count" id="cnt-recognitions">-</span>
    </div>
  </div>

  <!-- 右侧内容 -->
  <div class="content">
    <div class="content-header">
      <span class="content-title" id="content-title">选择左侧分类</span>
      <span class="content-subtitle" id="content-subtitle"></span>
    </div>
    <div class="content-body" id="content-body">
      <div class="empty-hint">← 从左侧选择要查看的内容</div>
    </div>
  </div>

</div>

<script>
let _currentSection = null
let _eventsData = [], _recognitionsData = []
let _selectedFile = null

// ── 初始化 ────────────────────────────────────────────────────────────────────
async function init() {
  // 预加载文件数量
  const [ev, rc] = await Promise.all([
    fetch('/memory/files?type=events').then(r=>r.json()),
    fetch('/memory/files?type=recognitions').then(r=>r.json()),
  ])
  _eventsData = ev.files
  _recognitionsData = rc.files
  document.getElementById('cnt-events').textContent = ev.files.length
  document.getElementById('cnt-recognitions').textContent = rc.files.length
}
init()

function refreshCurrent() {
  if (_currentSection) showSection(_currentSection)
}

// ── 导航 ──────────────────────────────────────────────────────────────────────
function showSection(sec) {
  _currentSection = sec
  _selectedFile = null
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'))
  document.getElementById('nav-' + sec).classList.add('active')
  const body = document.getElementById('content-body')
  body.innerHTML = '<div class="empty-hint">加载中…</div>'
  const handlers = {
    purpose:      showPurpose,
    index:        showIndex,
    keywords:     showKeywords,
    events:       () => showFileSection('events'),
    recognitions: () => showFileSection('recognitions'),
  }
  handlers[sec]?.()
}

// ── Purpose ──────────────────────────────────────────────────────────────────
async function showPurpose() {
  setHeader('Purpose', 'purpose.md')
  const d = await fetch('/memory/purpose').then(r=>r.json())
  document.getElementById('content-body').innerHTML = `
    <div style="max-width:600px">
      <div style="font-size:12px;color:#6b7280;margin-bottom:8px">Agent 的最高层目标，只能通过 Reflection 机制修改。</div>
      <textarea class="purpose-textarea" id="purpose-ta" rows="6">${esc(d.content)}</textarea>
      <br>
      <button class="save-btn" onclick="savePurpose()">保存</button>
      <span class="save-msg" id="save-msg"></span>
    </div>`
}
async function savePurpose() {
  const content = document.getElementById('purpose-ta').value.trim()
  const resp = await fetch('/memory/purpose', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({content})})
  const d = await resp.json()
  const msg = document.getElementById('save-msg')
  if (d.ok) { msg.textContent = '✓ 已保存'; setTimeout(()=>msg.textContent='', 2000) }
  else       { msg.textContent = '保存失败：' + d.reason; msg.style.color='#f87171' }
}

// ── Memory Index ──────────────────────────────────────────────────────────────
async function showIndex() {
  setHeader('Memory Index', 'memory/Memory.md')
  const d = await fetch('/memory/index-data').then(r=>r.json())
  if (!d.entries.length) {
    document.getElementById('content-body').innerHTML = '<div class="empty-hint">暂无记忆条目。</div>'
    return
  }
  const rows = d.entries.map(e => {
    const imp = parseInt(e.importance)
    const cls = imp >= 7 ? 'imp-high' : imp >= 4 ? 'imp-mid' : 'imp-low'
    const time = e.time.replace('T',' ').replace('+00:00','')
    return `<tr>
      <td class="td-name"><span style="cursor:pointer;color:#93c5fd" onclick="openFileByPath('${esc(e.path)}')">${esc(e.name)}</span></td>
      <td>${esc(e.description)}</td>
      <td class="td-imp"><span class="imp-badge ${cls}">${imp}</span></td>
      <td class="td-time">${esc(time)}</td>
    </tr>`
  }).join('')
  document.getElementById('content-body').innerHTML = `
    <table class="mem-table">
      <thead><tr><th>文件</th><th>摘要</th><th>Imp</th><th>时间</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`
}

// ── Keywords ──────────────────────────────────────────────────────────────────
async function showKeywords() {
  setHeader('Keywords', 'memory/keywords.md')
  const d = await fetch('/memory/keywords-data').then(r=>r.json())
  if (!d.rows.length) {
    document.getElementById('content-body').innerHTML = '<div class="empty-hint">暂无关键词。</div>'
    return
  }
  const rows = d.rows.map(r => {
    const chips = r.files.map(f => `<span class="kw-file-chip" onclick="openFileByPath('${esc(f)}')" title="${esc(f)}">${esc(f.split('/').pop())}</span>`).join('')
    return `<tr>
      <td class="kw-word">${esc(r.keyword)}</td>
      <td class="kw-count">${r.count}</td>
      <td>${r.files.length}</td>
      <td class="kw-files">${chips}</td>
    </tr>`
  }).join('')
  document.getElementById('content-body').innerHTML = `
    <table class="kw-table">
      <thead><tr><th>关键词</th><th style="text-align:center">频次</th><th>文件数</th><th>关联文件</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`
}

// ── Events / Recognitions ─────────────────────────────────────────────────────
async function showFileSection(type) {
  const label = type === 'events' ? 'Events' : 'Recognitions'
  setHeader(label, `memory/${type}/`)
  const d = await fetch(`/memory/files?type=${type}`).then(r=>r.json())
  if (type === 'events') _eventsData = d.files
  else _recognitionsData = d.files
  document.getElementById(`cnt-${type}`).textContent = d.files.length

  const body = document.getElementById('content-body')
  body.style.padding = '0'
  body.style.overflow = 'hidden'
  body.style.display = 'flex'
  body.innerHTML = `
    <div class="file-viewer">
      <div class="file-viewer-list" id="fv-list"></div>
      <div class="file-viewer-detail" id="fv-detail">
        <div class="empty-hint">← 点击左侧文件查看内容</div>
      </div>
    </div>`

  renderFileList(d.files, type)
}

function resetContentBodyStyle() {
  const body = document.getElementById('content-body')
  body.style.padding = '20px'
  body.style.overflow = 'auto'
  body.style.display = 'block'
}

function renderFileList(files, type) {
  const list = document.getElementById('fv-list')
  if (!files.length) { list.innerHTML = '<div class="empty-hint" style="padding:14px">暂无文件</div>'; return }
  list.innerHTML = files.map(f => {
    const imp = parseInt(f.importance) || 0
    const cls = imp >= 7 ? 'imp-high' : imp >= 4 ? 'imp-mid' : 'imp-low'
    const time = (f.time || '').replace('T',' ').slice(0, 16)
    return `<div class="file-card" id="card-${f.name}" onclick="viewFile('${esc(f.path)}', '${esc(f.name)}')">
      <div class="file-card-left">
        <div class="file-name">${esc(f.name)}</div>
        <div class="file-desc">${esc(f.description || '（无摘要）')}</div>
        <div class="file-meta">${esc(time)}</div>
      </div>
      <span class="imp-badge ${cls}">${imp}</span>
    </div>`
  }).join('')
}

async function viewFile(path, name) {
  _selectedFile = name
  document.querySelectorAll('.file-card').forEach(el => el.classList.remove('selected'))
  const card = document.getElementById('card-' + name)
  if (card) card.classList.add('selected')

  const detail = document.getElementById('fv-detail')
  detail.innerHTML = '<div class="empty-hint">加载中…</div>'
  const d = await fetch(`/memory/file?path=${encodeURIComponent(path)}`).then(r=>r.json())
  detail.innerHTML = renderFileContent(d.content)
}

async function openFileByPath(path) {
  // 判断类型并跳转到对应分区
  const type = path.startsWith('events/') ? 'events' : 'recognitions'
  const name = path.split('/').pop()
  await showFileSection(type)
  // 等 DOM 渲染后选中
  setTimeout(() => viewFile(path, name), 50)
}

function renderFileContent(text) {
  // 解析 frontmatter
  const fmMatch = text.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/)
  if (!fmMatch) return `<pre style="color:#d1d5db;font-size:13px;white-space:pre-wrap">${esc(text)}</pre>`

  const fmText = fmMatch[1]; const body = fmMatch[2].trim()
  const meta = {}
  fmText.split('\n').forEach(line => {
    const idx = line.indexOf(':')
    if (idx > 0) meta[line.slice(0, idx).trim()] = line.slice(idx+1).trim()
  })

  const imp = parseInt(meta.Importance) || 0
  const impCls = imp >= 7 ? 'imp-high' : imp >= 4 ? 'imp-mid' : 'imp-low'
  const kws = (meta.Keywords || '').replace(/[\[\]]/g, '')

  let fmHtml = `
    <div class="fm-grid">
      <span class="fm-key">摘要</span><span class="fm-val">${esc(meta.Description || '')}</span>
      <span class="fm-key">时间</span><span class="fm-val">${esc((meta.Time||'').replace('+00:00',''))}</span>
      <span class="fm-key">关键词</span><span class="fm-val kw">${esc(kws)}</span>
      <span class="fm-key">类型</span><span class="fm-val">${esc(meta.Type || '')}</span>
      <span class="fm-key">重要性</span><span class="fm-val"><span class="imp-badge ${impCls}">${imp}</span></span>
    </div>`

  // 解析正文 ## 段落
  let bodyHtml = ''
  const sections = body.split(/\n(?=##\s)/)
  sections.forEach(sec => {
    const lines = sec.split('\n')
    const heading = lines[0].replace(/^##\s*/, '').trim()
    const content = lines.slice(1).join('\n').trim()
    if (heading) {
      bodyHtml += `<div class="body-section"><h2>${esc(heading)}</h2><p>${esc(content)}</p></div>`
    } else if (content) {
      bodyHtml += `<div class="body-section"><p>${esc(content)}</p></div>`
    }
  })

  return fmHtml + bodyHtml
}

// ── 工具 ──────────────────────────────────────────────────────────────────────
function setHeader(title, subtitle) {
  document.getElementById('content-title').textContent = title
  document.getElementById('content-subtitle').textContent = subtitle
  resetContentBodyStyle()
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
