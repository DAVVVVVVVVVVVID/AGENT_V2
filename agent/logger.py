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
        """Log a loop emit message (thought / action / observation / etc.)."""
        t  = msg.get("type")
        ts = self._ts()
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
