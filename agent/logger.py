"""
AgentLogger — writes loop events, LLM prompts, and chat to a timestamped log file.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


class AgentLogger:
    def __init__(self, task: str, cfg: dict):
        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r'[^\w一-鿿]', '_', task)[:30]
        self._path = logs_dir / f"{ts}_{safe}.log"
        self._f    = open(self._path, "w", encoding="utf-8")
        self._write_header(task, cfg)

    @property
    def path(self) -> str:
        return str(self._path)

    # ── internal ──────────────────────────────────────────────────────────────

    def _ts(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _write_header(self, task: str, cfg: dict) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._f.write("=" * 80 + "\n")
        self._f.write(f"AGENT LOG  |  {now}\n")
        self._f.write(f"Task  : {task}\n")
        self._f.write(f"Agent : {cfg['name']} ({cfg.get('entity_id', '-')})\n")
        self._f.write(f"Model : {cfg['model']}\n")
        self._f.write(f"Vision: {cfg['vision_size']}×{cfg['vision_size']}\n")
        self._f.write("=" * 80 + "\n\n")
        self._f.flush()

    # ── public API ────────────────────────────────────────────────────────────

    def log_round(self, n: int) -> None:
        self._f.write(f"\n{'─' * 60}\n")
        self._f.write(f"  ROUND {n}   ({self._ts()})\n")
        self._f.write(f"{'─' * 60}\n")
        self._f.flush()

    def log_emit(self, msg: dict) -> None:
        """Log a loop emit message — all types shown in UI."""
        t  = msg.get("type")
        ts = self._ts()

        # ── 基础循环 ──
        if t == "thought":
            self._f.write(f"\n[{ts}] THOUGHT\n{msg['content']}\n")
        elif t == "action":
            self._f.write(f"\n[{ts}] ACTION\n{msg['content']}\n")
        elif t == "observation":
            self._f.write(f"\n[{ts}] OBSERVATION\n{msg['content']}\n")
        elif t == "finish":
            self._f.write(f"\n[{ts}] FINISH\n{msg['reply']}\n")
        elif t == "warning":
            self._f.write(f"\n[{ts}] WARNING\n{msg['content']}\n")
        elif t in ("paused", "resumed"):
            self._f.write(f"\n[{ts}] {t.upper()}\n")
        elif t == "user_inject":
            self._f.write(f"\n[{ts}] USER INJECT\n{msg['content']}\n")

        # ── 轮次 / 外层循环 ──
        elif t == "outer_start":
            self._f.write(f"\n[{ts}] LOOP START\n")
        elif t == "round_start":
            n = msg.get("n", "?")
            self._f.write(f"\n{'─' * 60}\n  ROUND {n}   ({ts})\n{'─' * 60}\n")

        # ── Plan ──
        elif t == "plan_start":
            self._f.write(f"\n[{ts}] PLAN START\n{msg.get('plan', '')}\n")
        elif t in ("plan_batch", "plan_batch_from_file"):
            suffix = " (file)" if t == "plan_batch_from_file" else ""
            plans  = msg.get("plans", [])
            lines  = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(plans))
            self._f.write(f"\n[{ts}] PLANS{suffix}\n{lines}\n")
        elif t == "plan_finish":
            self._f.write(f"\n[{ts}] PLAN FINISH\n{msg.get('reply', '')}\n")
        elif t == "plan_interrupted":
            self._f.write(f"\n[{ts}] PLAN INTERRUPTED\n{msg.get('plan', '')}\n")

        # ── Action sequence / result ──
        elif t == "action_sequence":
            lines = []
            for a in msg.get("actions", []):
                args = ", ".join(f"{k}={v!r}" for k, v in a.get("arguments", {}).items())
                lines.append(f"  → {a['name']}({args})")
            self._f.write(f"\n[{ts}] ACTION SEQUENCE\n" + "\n".join(lines) + "\n")
        elif t == "action_result":
            lines = []
            for a in msg.get("snapshot", []):
                s = a.get("status")
                if s == "success":
                    lines.append(f"  ✓ {a['name']}: {a.get('result', '')}")
                elif s == "failed":
                    lines.append(f"  ✗ {a['name']}: {a.get('reason', '')}")
                else:
                    lines.append(f"  … {a['name']}: 未执行")
            self._f.write(f"\n[{ts}] ACTION RESULT\n" + "\n".join(lines) + "\n")

        # ── Chat ──
        elif t == "chat_retrieve":
            stage = {
                "initial_behavior": "阶段一·近期行为",
                "initial_partner":  "阶段一·对话对象",
                "dynamic":          "阶段二·当前对话",
                "initial":          "阶段一",
            }.get(msg.get("stage", ""), msg.get("stage", ""))
            kws   = "、".join(msg.get("keywords", [])) or "（无）"
            hits  = "\n  ".join(msg.get("hits", [])) or "（无命中）"
            self._f.write(f"\n[{ts}] CHAT RETRIEVE {stage}\n关键词: {kws}\n命中:\n  {hits}\n")
            if msg.get("prompt"):
                self._f.write(f"Prompt:\n{msg['prompt']}\n")
            if msg.get("raw"):
                self._f.write(f"LLM: {msg['raw']}\n")
        elif t == "chat_waiting":
            self._f.write(f"\n[{ts}] CHAT WAITING\n")
        elif t == "chat_judgment":
            verdict = "接受" if msg.get("accept") else "拒绝"
            self._f.write(f"\n[{ts}] CHAT JUDGMENT  {verdict} — {msg.get('message', '')}\n")
            if msg.get("raw_response"):
                self._f.write(f"LLM: {msg['raw_response']}\n")
        elif t == "chat_session_start":
            self._f.write(f"\n[{ts}] CHAT SESSION START  room={msg.get('chat_room_id', '')}\n")
        elif t == "chat_speak":
            self._f.write(f"\n[{ts}] CHAT SPEAK\n{msg.get('content', '')}\n")
            if msg.get("raw_response"):
                self._f.write(f"LLM: {msg['raw_response']}\n")
        elif t == "chat_wait":
            self._f.write(f"\n[{ts}] CHAT WAIT  streak={msg.get('streak', 0)}\n")
        elif t == "chat_exit":
            self._f.write(f"\n[{ts}] CHAT EXIT  {msg.get('reason', '')}\n")
            if msg.get("raw_response"):
                self._f.write(f"LLM: {msg['raw_response']}\n")
        elif t == "chat_warning":
            self._f.write(f"\n[{ts}] CHAT WARNING\n{msg.get('content', '')}\n")
        elif t == "chat_event":
            self._f.write(f"\n[{ts}] CHAT EVENT  {msg.get('event', '')}\n")
        elif t == "chat_session_end":
            self._f.write(f"\n[{ts}] CHAT SESSION END  reason={msg.get('exit_reason', '')}\n")
        elif t == "chat_aftermath_start":
            self._f.write(f"\n[{ts}] CHAT AFTERMATH START\n")
        elif t == "chat_memory_saved":
            self._f.write(f"\n[{ts}] CHAT MEMORY SAVED  {msg.get('path', '')}\n")
        elif t == "chat_reorient":
            self._f.write(f"\n[{ts}] CHAT REORIENT  needs={msg.get('needs_reorient', False)}\n{msg.get('hint', '')}\n")
        elif t == "chat_done_replan":
            self._f.write(f"\n[{ts}] CHAT DONE REPLAN\n")
        elif t == "chat_aftermath_done":
            self._f.write(f"\n[{ts}] CHAT AFTERMATH DONE\n")

        # ── Dream ──
        elif t == "dream_start":
            self._f.write(f"\n[{ts}] DREAM START\n")
        elif t == "dream_triggered_by_chat":
            self._f.write(f"\n[{ts}] DREAM TRIGGERED BY CHAT\n")
        elif t == "dream_step":
            self._f.write(f"\n[{ts}] DREAM STEP  {msg.get('step', '')}\n{msg.get('summary', '')}\n")
        elif t == "dream_end":
            self._f.write(f"\n[{ts}] DREAM END  {msg.get('purpose_action', '')}\n")

        self._f.flush()

    def log_prompt(self, system: str, user: str) -> None:
        """Log the full system + user prompt sent to the LLM."""
        ts = self._ts()
        self._f.write(f"\n{'·' * 60}\n")
        self._f.write(f"[{ts}] LLM PROMPT\n")
        self._f.write(f"{'·' * 60}\n")
        self._f.write("── SYSTEM ──\n")
        self._f.write(system + "\n")
        self._f.write("\n── USER ──\n")
        self._f.write(user + "\n")
        self._f.write(f"{'·' * 60}\n")
        self._f.flush()

    def log_llm_result(self, thought: str, tool_name: str, arguments: dict) -> None:
        """Log the LLM's chosen tool call and reasoning."""
        ts      = self._ts()
        args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        self._f.write(f"\n[{ts}] LLM RESULT\n")
        if thought:
            self._f.write(f"Thought : {thought}\n")
        self._f.write(f"Tool    : {tool_name}({args_str})\n")
        self._f.flush()

    def log_chat(self, user_msg: str, agent_reply: str, injected: bool) -> None:
        """Log a user-initiated chat exchange during pause."""
        ts = self._ts()
        self._f.write(f"\n[{ts}] USER CHAT\n")
        self._f.write(f"User : {user_msg}\n")
        self._f.write(f"Agent: {agent_reply}\n")
        if injected:
            self._f.write("→ Injected into agent memory\n")
        self._f.flush()

    def close(self) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._f.write(f"\n{'=' * 80}\n")
        self._f.write(f"END  |  {now}\n")
        self._f.write("=" * 80 + "\n")
        self._f.close()
