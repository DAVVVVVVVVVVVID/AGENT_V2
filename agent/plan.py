"""
plan.py — 规划者 LLM 调用，输出有序 Plan Batch。

角色定位：长期规划者，关注目标分解，思考粒度粗。
与 think.py（执行者）使用不同 prompt 和输出格式。
"""

from __future__ import annotations

import json

from agent.memory import store
from agent.think import _format_arena_tree, _format_perception

# ── LLM 工具定义 ──────────────────────────────────────────────────────────────

_PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": "set_plans",
        "description": "设定本阶段要完成的 Plan 列表（有序）",
        "parameters": {
            "type": "object",
            "properties": {
                "plans": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "有序的 Plan 列表，每个 Plan 是一个明确、可执行的目标描述。"
                        "按优先级或自然顺序排列，至少 1 个。"
                    ),
                    "minItems": 1,
                },
            },
            "required": ["plans"],
        },
    },
}

# ── Prompt 构建 ───────────────────────────────────────────────────────────────

def _build_system_prompt(name: str) -> str:
    memory_index = store.load_memory_index()
    memory_section = (
        f"\n【记忆索引】\n{memory_index}" if "- [" in memory_index else ""
    )
    return (
        f"你是{name}的规划助手，负责根据最高目标（Purpose）制定当前阶段的行动计划。\n\n"
        "【规划原则】\n"
        "- 将 Purpose 分解为若干个具体、可执行的 Plan\n"
        "- 每个 Plan 是一个明确的目标描述（如「去厨房吃东西」），不涉及具体步骤\n"
        "- 综合考虑当前感知、过去记忆，制定符合实际情况的计划\n"
        "- 计划数量适中（建议 2–5 个），按执行顺序排列\n"
        f"{memory_section}\n\n"
        "通过 set_plans tool call 输出有序 Plan 列表，不要输出纯文字。"
    )


def _build_user_message(
    name: str,
    purpose: str,
    perceive_result: dict,
    retrieved_memories: list[str],
) -> str:
    parts = [
        f"【角色】\n{name}",
        f"【Purpose（最高目标）】\n{purpose}",
    ]

    if retrieved_memories:
        mem_text = "\n\n---\n\n".join(retrieved_memories)
        parts.append(f"【检索到的相关记忆】\n{mem_text}")

    parts.append(f"【当前感知】\n{_format_perception(perceive_result)}")
    return "\n\n".join(parts)


# ── Planner 类 ────────────────────────────────────────────────────────────────

class Planner:
    def __init__(
        self,
        name: str,
        llm,
        model: str,
        agent_logger=None,
    ):
        self._name   = name
        self._llm    = llm
        self._model  = model
        self._logger = agent_logger

    def generate(
        self,
        purpose: str,
        perceive_result: dict,
        retrieved_memories: list[str] | None = None,
    ) -> list[str]:
        """
        根据 Purpose + 感知 + 检索记忆，生成有序 Plan 列表。
        返回 list[str]，至少 1 个 Plan。
        """
        system   = _build_system_prompt(self._name)
        user_msg = _build_user_message(
            self._name, purpose, perceive_result, retrieved_memories or []
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_msg},
        ]

        if self._logger:
            self._logger.log_prompt(system, user_msg)

        msg = None
        for _ in range(3):
            resp = self._llm.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=[_PLAN_TOOL],
                tool_choice={"type": "function", "function": {"name": "set_plans"}},
            )
            msg = resp.choices[0].message
            if msg.tool_calls:
                break
        else:
            raise RuntimeError(
                f"Planner LLM returned no tool call after 3 attempts. content={msg.content!r}"
            )

        plans = json.loads(msg.tool_calls[0].function.arguments).get("plans", [])

        if not plans:
            raise RuntimeError("Planner returned empty plan list.")

        if self._logger:
            self._logger.log_llm_result("", "set_plans", {"plans": plans})

        return plans
