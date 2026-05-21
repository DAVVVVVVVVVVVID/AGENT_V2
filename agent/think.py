"""
Think module — executor LLM, outputs an Action Sequence (multiple tool_calls).
"""

from __future__ import annotations

import json

from openai import OpenAI

from agent.memory import store
from agent.personality import ocean_to_description

# ── Tool definitions ──────────────────────────────────────────────────────────

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_arena_tiles",
            "description": "获取指定 arena 内所有 tile 的坐标列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "arena_id": {"type": "string", "description": "目标 arena 的 ID"},
                },
                "required": ["arena_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_object_position",
            "description": "获取指定 object 的坐标（锚点位置）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "object_id": {"type": "string", "description": "目标 object 的 ID"},
                },
                "required": ["object_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_to_tile",
            "description": "移动到指定坐标的 tile。",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "目标 x 坐标"},
                    "y": {"type": "integer", "description": "目标 y 坐标"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_direction",
            "description": "向某方向移动 N 格，逐格校验可行走性，遇阻停止。",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "left", "right"],
                        "description": "移动方向",
                    },
                    "steps": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "最多移动格数",
                    },
                },
                "required": ["direction", "steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn",
            "description": "转向某方向，不移动。",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "left", "right"],
                    },
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "use_object",
            "description": "使用正前方的对象（需先面向该对象）。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "observe_object",
            "description": "阅读正前方对象的描述，不改变任何状态。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leave_object",
            "description": "退出当前正在使用的对象，恢复 idle 状态。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_to_area",
            "description": "移动到目标区域内随机一个可行走位置。",
            "parameters": {
                "type": "object",
                "properties": {
                    "area_type": {
                        "type": "string",
                        "enum": ["arena", "sector", "world"],
                        "description": "区域类型",
                    },
                    "area_id": {
                        "type": "string",
                        "description": "区域 ID",
                    },
                },
                "required": ["area_type", "area_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "当前 Plan 已完成时调用，必须是序列中最后一个行动。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reply": {
                        "type": "string",
                        "description": "对当前 Plan 目标的总结回复",
                    },
                },
                "required": ["reply"],
            },
        },
    },
]

_VALID_TOOL_NAMES = {t["function"]["name"] for t in _TOOLS}

# ── Formatting helpers ────────────────────────────────────────────────────────

def _format_arena_tree(tree: dict | None) -> str:
    if tree is None:
        return "（未知区域）"

    def _label(node: dict) -> str:
        name = node.get("name", "")
        nid  = node.get("id", "")
        return f"{name}(ID:{nid})" if name and name != nid else f"(ID:{nid})"

    sector_node = tree.get("sector")
    if not sector_node:
        return f"[世界] {_label(tree)}"

    arenas = sector_node.get("arenas", [])
    lines  = [
        f"[世界]  {_label(tree)}",
        f"[区域]  {_label(sector_node)}",
    ]
    for arena in arenas:
        current_mark = "  ← 当前位置" if arena.get("current") else ""
        objects      = arena.get("objects", [])
        obj_str = "、".join(
            f"{o['name']}（{'可交互' if o['interactable'] else '不可交互'}，ID:{o['id']}）"
            for o in objects
        ) if objects else "无对象"
        lines.append(f"  [场所] {_label(arena)}{current_mark}")
        lines.append(f"         对象：{obj_str}")
    return "\n".join(lines)


def _format_perception(perceive_result: dict) -> str:
    ps  = perceive_result["player_state"]
    pos = ps["position"]
    facing_map = {"up": "上", "down": "下", "left": "左", "right": "右"}
    facing     = facing_map.get(ps["facing"], ps["facing"])

    front      = perceive_result["front_object"]
    front_desc = (
        f"正前方：{front['name']}（ID: {front['id']}）" if front else "正前方：无对象"
    )
    diff      = perceive_result["state_diff"]
    diff_desc = (
        "状态变化：" + "、".join(f"{k}={v}" for k, v in diff.items())
        if diff else "状态无变化"
    )
    state_label = f"，当前使用：{ps['stateLabel']}" if ps.get("stateLabel") else ""

    return (
        f"位置：({pos['x']}, {pos['y']})，朝向：{facing}\n"
        f"hp: {ps['hp']}，energy: {ps['energy']}，状态: {ps['state']}{state_label}\n"
        f"{front_desc}\n"
        f"{diff_desc}\n"
        f"视野 tile 数：{len(perceive_result['vision_tiles'])}\n"
        f"\n【环境结构（世界→区域→场所→对象）】\n{_format_arena_tree(perceive_result['arena_tree'])}"
    )


def _format_action_sequence(seq: list[dict]) -> str:
    lines = []
    for a in seq:
        status = a.get("status", "")
        name   = a.get("name", "")
        args   = a.get("arguments", {})
        if status == "success":
            detail = str(a.get("result", ""))
            lines.append(f"    ✓ {name}({args}) → {detail}")
        elif status == "failed":
            lines.append(f"    ✗ {name}({args}) → 失败：{a.get('reason', '')}")
        else:
            lines.append(f"    … {name}({args}) → 未执行")
    return "\n".join(lines)


def _build_system_prompt(
    name: str,
    ocean: dict,
    lifestyle: list[str],
    common_sense: list[str],
) -> str:
    personality       = ocean_to_description(ocean["O"], ocean["C"], ocean["E"], ocean["A"], ocean["N"])
    lifestyle_text    = "\n".join(f"- {item}" for item in lifestyle)
    common_sense_text = "\n".join(f"- {item}" for item in common_sense)
    memory_index      = store.load_memory_index()
    memory_section    = (
        f"\n【记忆索引】\n{memory_index}" if "- [" in memory_index else ""
    )
    return (
        f"你是{name}，一个生活在虚拟世界中的角色。\n\n"
        f"【性格特征】\n{personality}\n\n"
        f"【生活方式】\n{lifestyle_text}\n\n"
        f"【常识】\n{common_sense_text}\n"
        f"{memory_section}\n\n"
        "根据当前 Plan、感知信息和历史记忆，规划并输出本轮的行动序列。\n"
        "可以一次输出多个原子行动（tool call），按执行顺序排列。\n"
        "若当前 Plan 已完成，最后一个行动必须是 finish()。\n"
        "所有行动均通过 tool call 输出，不要输出纯文字回复。"
    )


def _build_user_message(
    plan: str,
    history: list[dict],
    perceive_result: dict,
    retrieved_memories: list[str],
) -> str:
    parts = [f"【当前 Plan】\n{plan}"]

    if history:
        lines = ["【历史轮次】"]
        for i, h in enumerate(history, 1):
            lines.append(f"第{i}轮：")
            lines.append(f"  思考：{h.get('thought', '')}")
            if "action_sequence" in h:
                lines.append("  行动序列：")
                lines.append(_format_action_sequence(h["action_sequence"]))
        parts.append("\n".join(lines))

    if retrieved_memories:
        mem_text = "\n\n---\n\n".join(retrieved_memories)
        parts.append(f"【检索到的相关记忆】\n{mem_text}")

    parts.append(f"【当前感知】\n{_format_perception(perceive_result)}")
    return "\n\n".join(parts)


def _extract_thought(msg) -> str:
    for attr in ("reasoning", "reasoning_content"):
        val = getattr(msg, attr, None)
        if val:
            return val.strip()
    extra = getattr(msg, "model_extra", None) or {}
    for key in ("reasoning", "reasoning_content"):
        if extra.get(key):
            return extra[key].strip()
    return (msg.content or "").strip()


# ── Think class ───────────────────────────────────────────────────────────────

class Think:
    def __init__(
        self,
        name: str,
        ocean: dict,
        lifestyle: list[str],
        common_sense: list[str] | None = None,
        llm_base_url: str = "http://localhost:11435/v1",
        model: str = "qwen3:32b",
        agent_logger=None,
    ):
        self._name      = name
        self._ocean     = ocean
        self._lifestyle = lifestyle
        self._common_sense = common_sense or []
        self._llm       = OpenAI(base_url=llm_base_url, api_key="ollama")
        self._model     = model
        self._logger    = agent_logger

    def think(
        self,
        plan: str,
        history: list[dict],
        perceive_result: dict,
        retrieved_memories: list[str] | None = None,
    ) -> dict:
        """
        Call LLM and return:
          {
            "thought": str,
            "action_sequence": [{"name": str, "arguments": dict}, ...]
          }
        Memory.md is reloaded each call so the index is always current.
        """
        system  = _build_system_prompt(self._name, self._ocean, self._lifestyle, self._common_sense)
        user_msg = _build_user_message(plan, history, perceive_result, retrieved_memories or [])
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
                tools=_TOOLS,
                tool_choice="required",
            )
            msg = resp.choices[0].message
            if msg.tool_calls:
                break
        else:
            raise RuntimeError(
                f"LLM returned no tool call after 3 attempts. content={msg.content!r}"
            )

        thought = _extract_thought(msg)

        action_sequence = []
        for tc in msg.tool_calls:
            name = tc.function.name
            if name not in _VALID_TOOL_NAMES:
                raise RuntimeError(f"LLM returned unknown tool: {name!r}")
            action_sequence.append({
                "name":      name,
                "arguments": json.loads(tc.function.arguments),
            })

        if self._logger:
            self._logger.log_llm_result(thought, str(action_sequence), {})

        return {
            "thought":         thought,
            "action_sequence": action_sequence,
        }
