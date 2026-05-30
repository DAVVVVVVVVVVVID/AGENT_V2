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
            "description": (
                "获取指定 arena 内所有 tile 的坐标列表。"
                "用于在不清楚具体目标坐标时探索某个场所的可用位置，"
                "获取后可从中挑选合适的 tile 再调用 move_to_tile 前往。"
            ),
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
            "description": (
                "获取指定 object 的锚点坐标，同时返回其周围所有可行走的相邻格子列表（adjacent_walkable）。"
                "重要：object 本身占据的格子不可行走，不能直接 move_to_tile 到 object 的坐标。"
                "正确流程：调用本工具获取 adjacent_walkable → 从中选一个格子 move_to_tile → turn 面向 object → use_object 或 observe_object。"
            ),
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
            "description": (
                "移动到指定坐标的 tile。"
                "这是有明确目标时的首选移动方式，大多数目标移动都应使用此工具。"
                "适用场景：已知目标坐标（来自 get_object_position、get_arena_tiles 等）时直接前往。"
                "不适合：目标坐标未知时的探索或试探性移动（用 move_direction）；跨区域移动（用 move_to_area）。"
            ),
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
            "description": (
                "向某方向移动最多 N 格，逐格校验可行走性，遇阻自动停止。"
                "适用场景：无具体目标坐标时的探索、闲逛、试探性移动，或需要微调当前位置时。"
                "不适合：已知目标坐标的移动（用 move_to_tile 更精确高效）；跨区域移动（用 move_to_area）。"
            ),
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
            "description": (
                "原地转向某方向，不产生移动。"
                "use_object 和 observe_object 要求必须面向目标 object，因此在调用它们之前必须先用 turn 调整朝向。"
            ),
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
            "description": (
                "与正前方的 object 进行交互，触发其功能（如使用工具、进入场景、执行操作等），会改变游戏状态。"
                "严格前置条件（缺一不可）：① 已移动到该 object 的相邻可行走格（adjacent_walkable 中的某个坐标）；② 已 turn 面向该 object。"
                "与 observe_object 的区别：observe_object 只读取信息不改变状态；use_object 触发真实交互。"
                "使用后如需离开，调用 leave_object 恢复 idle 状态。"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "observe_object",
            "description": (
                "读取正前方 object 的描述信息，不触发任何交互，不改变任何状态。"
                "适用场景：想了解某个 object 是什么、有什么功能，但尚未决定是否使用时。"
                "前置条件与 use_object 相同：需已移动到相邻格并 turn 面向目标。"
                "与 use_object 的区别：本工具只读信息；use_object 才真正触发交互。"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leave_object",
            "description": (
                "退出当前正在使用/占用的 object，将状态恢复为 idle。"
                "在完成一个 object 的使用后，必须调用本工具才能自由移动或使用其他 object。"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_to_area",
            "description": (
                "跨区域移动：移动到目标区域（arena / sector / world）内距离当前位置最近的可行走 tile。"
                "适用场景：已知目标区域 ID，需要前往该区域但不关心具体落点时。"
                "不适合：已知具体目标坐标（用 move_to_tile）；在当前区域内的局部移动（用 move_to_tile 或 move_direction）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "area_type": {
                        "type": "string",
                        "enum": ["arena", "sector", "world"],
                        "description": "区域类型：arena（具体场所）、sector（区域）、world（整个世界）",
                    },
                    "area_id": {
                        "type": "string",
                        "description": "目标区域的 ID",
                    },
                },
                "required": ["area_type", "area_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_recognition",
            "description": (
                "记录一条你自己的主观认知——对事物的看法、规律总结、行动反省、感受或洞察。"
                "这是你的'内心独白'工具：记录的是你对世界的理解，而非客观事实的陈述。"
                "可在行动序列中任意时刻调用，不必等到 finish 之前；没有真实所得时不必强制调用。"
                "记录的内容应对未来的你有参考价值：下次遇到类似情况时能从记忆中检索到并加以利用。"
                "不会中断后续行动——调用后序列继续执行。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "一句话概括这条认知的核心，将显示在记忆索引中（15字以内为佳）",
                    },
                    "content": {
                        "type": "string",
                        "description": "认知的具体内容，第一人称，自然语言，可包含原因、推断、感受等",
                    },
                    "trigger": {
                        "type": "string",
                        "description": "触发此认知的事件或情境，如'尝试使用热水机失败后'（可选）",
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "关键词列表，用于未来检索（2-5个）",
                    },
                    "importance": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "重要程度：1=一般，3=重要，5=非常重要",
                    },
                },
                "required": ["summary", "content", "keywords", "importance"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": (
                "宣告当前 Plan 已完成，必须且只能作为行动序列中的最后一个行动。"
                "只有在 Plan 目标真正达成后才能调用，不能提前或中途调用。"
                "调用后本轮 Plan 结束，系统将进入下一个 Plan。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reply": {
                        "type": "string",
                        "description": "对本次 Plan 执行结果的简要总结",
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


def _format_vision(vision_tiles: list[dict], px: int, py: int) -> str:
    if not vision_tiles:
        return ""

    tile_map = {(t["x"], t["y"]): t for t in vision_tiles}
    xs = [t["x"] for t in vision_tiles]
    ys = [t["y"] for t in vision_tiles]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    rows = []
    for y in range(min_y, max_y + 1):
        row = []
        for x in range(min_x, max_x + 1):
            if x == px and y == py:
                row.append("@")
            elif (x, y) in tile_map:
                t = tile_map[(x, y)]
                row.append("O" if t.get("object") else ("·" if t["walkable"] else "#"))
            else:
                row.append("?")
        rows.append(" ".join(row))

    grid = "\n".join(rows)

    obj_tiles = [t for t in vision_tiles if t.get("object")]
    if obj_tiles:
        lines = []
        for t in obj_tiles:
            arena_id  = t.get("arena") or ""
            arena_str = f"区域:{arena_id}" if arena_id else "未知区域"
            obj       = t["object"]
            walkable  = "可走" if t["walkable"] else "不可走"
            lines.append(f"  ({t['x']},{t['y']}) {obj['name']}(ID:{obj['id']}) [{walkable}] — {arena_str}")
        obj_section = "【视野内对象】\n" + "\n".join(lines)
    else:
        obj_section = "【视野内对象】无"

    return f"【视野】（· 可走  # 不可走  O 有对象  @ 自身）\n{grid}\n\n{obj_section}"


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

    vision_str = _format_vision(
        perceive_result["vision_tiles"], pos["x"], pos["y"]
    )

    return (
        f"位置：({pos['x']}, {pos['y']})，朝向：{facing}\n"
        f"hp: {ps['hp']}，energy: {ps['energy']}，状态: {ps['state']}{state_label}\n"
        f"{front_desc}\n"
        f"{diff_desc}\n"
        f"\n{vision_str}\n"
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
