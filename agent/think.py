"""
Think module — builds prompt and calls LLM to produce a structured tool call.
"""

from __future__ import annotations

import json

from openai import OpenAI

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
            "description": "任务已完成时调用，终止循环并输出总结。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reply": {
                        "type": "string",
                        "description": "对原始任务目标的总结回复",
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
        return "未知区域"

    def _label(node: dict) -> str:
        name = node.get("name", "")
        nid  = node.get("id", "")
        return f"{name}(ID:{nid})" if name and name != nid else f"(ID:{nid})"

    sector_node = tree.get("sector")
    if not sector_node:
        return _label(tree)
    arena_node = sector_node.get("arena")
    if not arena_node:
        return f"{_label(tree)} > {_label(sector_node)}"
    objects = arena_node.get("objects", [])
    path = f"{_label(tree)} > {_label(sector_node)} > {_label(arena_node)}"
    if objects:
        obj_list = "、".join(
            f"{o['name']}（{'可交互' if o['interactable'] else '不可交互'}，ID:{o['id']}）"
            for o in objects
        )
        return f"{path}，包含对象：{obj_list}"
    return path


def _format_perception(perceive_result: dict) -> str:
    ps = perceive_result["player_state"]
    pos = ps["position"]
    facing_map = {"up": "上", "down": "下", "left": "左", "right": "右"}
    facing = facing_map.get(ps["facing"], ps["facing"])
    front = perceive_result["front_object"]
    front_desc = (
        f"正前方：{front['name']}（ID: {front['id']}）" if front else "正前方：无对象"
    )
    diff = perceive_result["state_diff"]
    diff_desc = (
        "状态变化：" + "、".join(f"{k}={v}" for k, v in diff.items())
        if diff else "状态无变化"
    )
    state_label = f"，当前使用：{ps['stateLabel']}" if ps.get("stateLabel") else ""
    return (
        f"位置：({pos['x']}, {pos['y']})，朝向：{facing}\n"
        f"所在区域：{_format_arena_tree(perceive_result['arena_tree'])}\n"
        f"视野 tile 数：{len(perceive_result['vision_tiles'])}\n"
        f"{front_desc}\n"
        f"{diff_desc}\n"
        f"hp: {ps['hp']}，energy: {ps['energy']}，状态: {ps['state']}{state_label}"
    )


def _build_system_prompt(
    name: str,
    ocean: dict,
    lifestyle: list[str],
    common_sense: list[str],
) -> str:
    personality = ocean_to_description(
        ocean["O"], ocean["C"], ocean["E"], ocean["A"], ocean["N"]
    )
    lifestyle_text    = "\n".join(f"- {item}" for item in lifestyle)
    common_sense_text = "\n".join(f"- {item}" for item in common_sense)
    return (
        f"你是{name}，一个生活在虚拟世界中的角色。\n\n"
        f"【性格特征】\n{personality}\n\n"
        f"【生活方式】\n{lifestyle_text}\n\n"
        f"【常识】\n{common_sense_text}\n\n"
        "根据当前感知和历史记忆，选择下一步行动。\n"
        "每次只能选择一个行动，必须通过 tool call 输出，不要输出纯文字回复。"
    )


def _build_user_message(
    task: str,
    history: list[dict],
    perceive_result: dict,
) -> str:
    parts = [f"【当前任务】\n{task}"]
    if history:
        lines = ["【历史记忆】"]
        for i, h in enumerate(history, 1):
            lines.append(f"第{i}轮：")
            lines.append(f"  思考：{h['thought']}")
            lines.append(f"  行动：{h['action']}")
            lines.append(f"  观察：{h['observation']}")
        parts.append("\n".join(lines))
    parts.append(f"【当前感知】\n{_format_perception(perceive_result)}")
    return "\n\n".join(parts)


def _extract_thought(msg) -> str:
    """Extract reasoning/thinking text from the LLM response message."""
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
        self._system = _build_system_prompt(name, ocean, lifestyle, common_sense or [])
        self._llm = OpenAI(base_url=llm_base_url, api_key="ollama")
        self._model = model
        self._logger = agent_logger

    def think(
        self,
        task: str,
        history: list[dict],
        perceive_result: dict,
    ) -> dict:
        """
        Call LLM and return:
          {"thought": str, "tool_call": {"name": str, "arguments": dict}}
        """
        user_msg = _build_user_message(task, history, perceive_result)
        messages = [
            {"role": "system", "content": self._system},
            {"role": "user",   "content": user_msg},
        ]
        if self._logger:
            self._logger.log_prompt(self._system, user_msg)

        msg = None
        for attempt in range(3):
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
            raise RuntimeError(f"LLM returned no tool call after 3 attempts. content={msg.content!r}")

        thought   = _extract_thought(msg)
        tc        = msg.tool_calls[0]
        name      = tc.function.name
        arguments = json.loads(tc.function.arguments)

        if name not in _VALID_TOOL_NAMES:
            raise RuntimeError(f"LLM returned unknown tool: {name!r}")

        if self._logger:
            self._logger.log_llm_result(thought, name, arguments)

        return {
            "thought":   thought,
            "tool_call": {
                "name":      name,
                "arguments": arguments,
            },
        }
