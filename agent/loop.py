"""
Loop controller — Perceive → Think → Execute → store history → repeat.
"""

from __future__ import annotations

import threading
from typing import Callable

from agent.perceive import Perceive
from agent.think import Think
from agent.execute import Execute

_MAX_HISTORY = 10


def _action_str(tool_call: dict) -> str:
    args = tool_call.get("arguments", {})
    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return f"{tool_call['name']}({args_str})"


def _default_emit(msg: dict) -> None:
    """Default emit: format structured messages as CLI text."""
    t = msg.get("type")
    if t == "round_start":
        print(f"\n{'─' * 60}")
        print(f"【第 {msg['round']} 轮】")
    elif t == "thought":
        content = msg["content"]
        print(f"思考：{content[:300]}{'…' if len(content) > 300 else ''}")
    elif t == "action":
        print(f"行动：{msg['content']}")
    elif t == "observation":
        print(f"观察：{msg['content']}")
    elif t == "finish":
        print(f"\n{'═' * 60}")
        print(f"任务完成：{msg['reply']}")
        print(f"{'═' * 60}")
    elif t == "warning":
        print(f"⚠️  {msg['content']}")
    elif t == "paused":
        print("⏸  循环已暂停，等待恢复…")
    elif t == "resumed":
        print("▶  循环已恢复。")


def run(
    task: str,
    perceiver: Perceive,
    thinker: Think,
    executor: Execute,
    emit: Callable[[dict], None] | None = None,
    pause_flag: threading.Event | None = None,
    shared_state: dict | None = None,
) -> str:
    """
    Run the ReAct loop until the agent calls finish or an error occurs.
    Returns the final reply string.

    emit: optional callback receiving structured dicts:
        {"type": "round_start", "round": int}
        {"type": "thought",     "content": str}
        {"type": "action",      "content": str}
        {"type": "observation", "content": str}
        {"type": "finish",      "reply": str}
        {"type": "warning",     "content": str}
        {"type": "paused"}
        {"type": "resumed"}

    pause_flag: threading.Event — set=running, cleared=paused.
        Loop blocks at end of each complete round when flag is cleared.

    shared_state: mutable dict shared with external callers (e.g. chat endpoint).
        Written keys: "history" (same list object), "perceive" (latest result).
    """
    if emit is None:
        emit = _default_emit

    history: list[dict] = []
    if shared_state is not None:
        shared_state["history"] = history  # share reference so external code can read/write

    round_num = 0

    while True:
        round_num += 1
        emit({"type": "round_start", "round": round_num})

        # ── Perceive ──────────────────────────────────────────────
        perceive_result = perceiver.perceive()
        if shared_state is not None:
            shared_state["perceive"] = perceive_result

        # ── Think ─────────────────────────────────────────────────
        try:
            think_result = thinker.think(task, history, perceive_result)
        except Exception as e:
            msg = f"Think 错误：{e}"
            emit({"type": "warning", "content": msg})
            history.append({"thought": "", "action": "（Think 失败）", "observation": msg})
            if len(history) > _MAX_HISTORY:
                history.pop(0)
            continue

        thought    = think_result["thought"]
        tool_call  = think_result["tool_call"]
        action_str = _action_str(tool_call)

        emit({"type": "thought", "content": thought})
        emit({"type": "action",  "content": action_str})

        # ── Execute ───────────────────────────────────────────────
        try:
            exec_result = executor.execute(tool_call)
        except Exception as e:
            msg = f"Execute 错误：{e}"
            emit({"type": "warning", "content": msg})
            history.append({"thought": thought, "action": action_str, "observation": msg})
            if len(history) > _MAX_HISTORY:
                history.pop(0)
            continue

        observation  = exec_result["observation"]
        is_finish    = exec_result["is_finish"]
        finish_reply = exec_result["finish_reply"]

        emit({"type": "observation", "content": observation})

        # ── store history ─────────────────────────────────────────
        history.append({
            "thought":     thought,
            "action":      action_str,
            "observation": observation,
        })
        if len(history) > _MAX_HISTORY:
            history.pop(0)

        # ── check finish ──────────────────────────────────────────
        if is_finish:
            emit({"type": "finish", "reply": finish_reply})
            return finish_reply

        # ── pause checkpoint ──────────────────────────────────────
        if pause_flag is not None and not pause_flag.is_set():
            emit({"type": "paused"})
            pause_flag.wait()        # blocks until resumed or stopped
            emit({"type": "resumed"})
