"""
memory/shadow.py — 影子 Agent，finish() 后异步触发，生成 Event 记忆。
在后台线程中运行，不阻塞主 agent。
"""

from __future__ import annotations

import json
import logging
import threading

from agent.memory import store

logger = logging.getLogger(__name__)

# ── LLM 工具定义 ──────────────────────────────────────────────────────────────

_RECORD_TOOL = {
    "type": "function",
    "function": {
        "name": "record_event",
        "description": "将本次 Plan 的执行过程记录为事件记忆",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "一句话摘要，概括本次 Plan 的核心内容",
                },
                "what": {
                    "type": "string",
                    "description": "发生了什么：Plan 的目标是什么，实际完成了什么",
                },
                "how": {
                    "type": "string",
                    "description": "怎么做到的：关键步骤、使用了哪些行动、遇到什么障碍",
                },
                "why": {
                    "type": "string",
                    "description": "为什么这样做：背后的 Purpose 或上下文原因",
                },
                "importance": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 10,
                    "description": "重要性评分 0–10（0–3日常琐事，4–6有参考价值，7–9重要，10极少数）",
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3–5 个关键词，用于后续检索",
                },
            },
            "required": ["summary", "what", "how", "why", "importance", "keywords"],
        },
    },
}

_SYSTEM_PROMPT = (
    "你是一个记忆整理助手。"
    "根据提供的 agent 行动历史，客观总结本次任务的执行情况，"
    "生成结构化的事件记忆记录。内容要简洁、客观，不要主观评价。"
)

# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _format_history(history: list[dict]) -> str:
    lines = []
    for i, h in enumerate(history, 1):
        lines.append(f"第{i}轮：")
        if "thought" in h:
            lines.append(f"  思考：{h['thought']}")
        # v2 格式：action_sequence 为列表快照
        if "action_sequence" in h:
            lines.append("  行动序列：")
            for a in h["action_sequence"]:
                status = a.get("status", "")
                detail = a.get("result") or a.get("reason") or ""
                lines.append(
                    f"    - {a['name']}({a.get('arguments', {})}) → {status}"
                    + (f"，{detail}" if detail else "")
                )
        elif "action" in h:
            lines.append(f"  行动：{h['action']}")
        if "observation" in h:
            lines.append(f"  观察：{h['observation']}")
    return "\n".join(lines)


def _run(history: list[dict], llm, model: str) -> None:
    """在后台线程中执行：调用 LLM 生成 Event 记忆，写入文件。"""
    try:
        history_text = _format_history(history)
        user_msg = f"以下是本次任务的完整行动历史：\n\n{history_text}"

        resp = llm.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            tools=[_RECORD_TOOL],
            tool_choice={"type": "function", "function": {"name": "record_event"}},
        )

        tc   = resp.choices[0].message.tool_calls[0]
        args = json.loads(tc.function.arguments)

        raw_actions = [
            a for h in history
            for a in h.get("action_sequence", [])
            if a.get("status") in ("success", "failed")
        ]

        fp = store.create_event(
            summary     = args["summary"],
            what        = args["what"],
            how         = args["how"],
            why         = args["why"],
            importance  = int(args["importance"]),
            keywords    = args["keywords"],
            raw_actions = raw_actions,
        )
        logger.info("shadow agent: event memory written → %s", fp.name)

    except Exception:
        logger.exception("shadow agent failed")


# ── 公开 API ──────────────────────────────────────────────────────────────────

def trigger(history: list[dict], llm, model: str) -> None:
    """触发影子 Agent 后台线程，主 agent 立即返回，不阻塞。"""
    t = threading.Thread(target=_run, args=(history, llm, model), daemon=True)
    t.start()
