"""
dream.py — Dream 机制：agent 的认知整理状态。

执行顺序：阅读 → 整合 → 提炼 → 更新 Purpose
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from agent.memory import store


# ── DreamConfig ───────────────────────────────────────────────────────────────

@dataclass
class DreamConfig:
    memory_count: int = -1
    time_minutes: int = -1
    time_of_day: str | None = None


# ── DreamTrigger ──────────────────────────────────────────────────────────────

class DreamTrigger:
    def __init__(self, config: DreamConfig):
        self._config = config
        self._tod_triggered_date: date | None = None

    def should_dream(self) -> bool:
        cfg = self._config
        if cfg.memory_count == -1 and cfg.time_minutes == -1 and cfg.time_of_day is None:
            return False

        last_dt = store.read_last_dream_time()
        now = datetime.now(timezone.utc)

        if cfg.memory_count != -1:
            base = last_dt if last_dt is not None else datetime.min.replace(tzinfo=timezone.utc)
            if store.get_new_memory_count(base) >= cfg.memory_count:
                return True

        if cfg.time_minutes != -1:
            if last_dt is None or (now - last_dt).total_seconds() / 60 >= cfg.time_minutes:
                return True

        if cfg.time_of_day is not None:
            today = now.date()
            if self._tod_triggered_date != today:
                try:
                    h, m = map(int, cfg.time_of_day.split(":"))
                except ValueError:
                    return False
                local_now = datetime.now()
                if (local_now.hour, local_now.minute) >= (h, m):
                    self._tod_triggered_date = today
                    return True

        return False


# ── LLM 工具定义 ──────────────────────────────────────────────────────────────

_CONSOLIDATE_TOOL = {
    "type": "function",
    "function": {
        "name": "set_consolidations",
        "description": "输出记忆整合操作列表。每个操作将一组相关记忆合并为一条整合记忆。",
        "parameters": {
            "type": "object",
            "properties": {
                "consolidations": {
                    "type": "array",
                    "description": "整合操作列表，可以为空数组表示无需整合",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["create", "update"],
                                "description": "create=新建整合记忆，update=更新已有整合记忆",
                            },
                            "description": {
                                "type": "string",
                                "description": "整合记忆的主题描述（15字以内）",
                            },
                            "content": {
                                "type": "string",
                                "description": "整合后的完整认知内容，综合所有来源记忆",
                            },
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "关键词列表（2-6个）",
                            },
                            "source_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "来源记忆的相对路径列表（相对于 memory/ 目录），仅用于 create",
                            },
                            "existing_path": {
                                "type": "string",
                                "description": "已有整合记忆的路径（相对于 memory/ 目录），仅用于 update",
                            },
                            "new_source_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "新增来源记忆路径列表，仅用于 update",
                            },
                        },
                        "required": ["action", "content"],
                    },
                },
            },
            "required": ["consolidations"],
        },
    },
}

_REFLECT_TOOL = {
    "type": "function",
    "function": {
        "name": "set_insights",
        "description": "输出从整合记忆中提炼出的高阶认知列表。可以为空数组表示无新洞察。",
        "parameters": {
            "type": "object",
            "properties": {
                "insights": {
                    "type": "array",
                    "description": "高阶认知列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "认知摘要（15字以内），将显示在记忆索引中",
                            },
                            "content": {
                                "type": "string",
                                "description": "认知的详细内容，第一人称，包含推理和洞察",
                            },
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "关键词列表（2-5个）",
                            },
                            "importance": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 10,
                                "description": "重要程度 1-10",
                            },
                            "source_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "支撑此认知的来源记忆路径列表（相对于 memory/ 目录）",
                            },
                        },
                        "required": ["summary", "content", "keywords", "importance", "source_paths"],
                    },
                },
            },
            "required": ["insights"],
        },
    },
}

_PURPOSE_TOOL = {
    "type": "function",
    "function": {
        "name": "set_purpose_update",
        "description": "根据整合后的记忆决定是否更新 Purpose。",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["keep", "modify", "replace"],
                    "description": "keep=不修改，modify=局部调整（仍需提供完整最终列表），replace=完全重写",
                },
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Purpose 条目的完整最终列表（action=keep 时可省略）",
                },
            },
            "required": ["action"],
        },
    },
}


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def _parse_frontmatter_field(text: str, field: str) -> str:
    m = re.search(rf"^{field}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _parse_importance(text: str) -> int:
    val = _parse_frontmatter_field(text, "Importance")
    try:
        return int(val)
    except ValueError:
        return 1


def _parse_type(text: str) -> str:
    return _parse_frontmatter_field(text, "Type")


def _read_all_memories() -> dict[str, str]:
    """从 Memory.md 读取所有记忆条目，返回 {rel_path: content} 字典。"""
    index_text = store.load_memory_index()
    memories: dict[str, str] = {}
    memory_dir = store.get_memory_dir()

    for line in index_text.splitlines():
        m = re.search(r"\[.+?\]\((.+?)\)", line)
        if not m:
            continue
        rel_path = m.group(1)
        fp = memory_dir / rel_path
        if fp.exists():
            memories[rel_path] = fp.read_text(encoding="utf-8")

    return memories


def _format_memories_for_llm(memories: dict[str, str]) -> str:
    """将记忆字典格式化为 LLM 可读的文本。"""
    parts = []
    for rel_path, content in memories.items():
        parts.append(f"[路径: {rel_path}]\n{content}")
    return "\n\n---\n\n".join(parts)


# ── Dream 类 ──────────────────────────────────────────────────────────────────

class Dream:
    def __init__(
        self,
        name: str,
        llm,
        model: str,
        emit: Callable[[dict], None] | None = None,
        agent_logger=None,
    ):
        self._name    = name
        self._llm     = llm
        self._model   = model
        self._emit    = emit or (lambda _: None)
        self._logger  = agent_logger

    def run(self) -> None:
        """执行完整 Dream 流程（四步）。"""
        self._emit({"type": "dream_start"})

        # Step 1: 阅读
        memories = self._read_memories()

        # Step 2: 整合
        memories = self._consolidate(memories)

        # Step 3: 提炼
        self._reflect(memories)

        # Step 4: 更新 Purpose
        purpose_action = self._update_purpose(memories)

        store.write_last_dream_time()
        self._emit({"type": "dream_end", "purpose_action": purpose_action})

    # ── Step 1: 阅读 ─────────────────────────────────────────────────────────

    def _read_memories(self) -> dict[str, str]:
        memories = _read_all_memories()
        self._emit({
            "type": "dream_step",
            "step": "read",
            "summary": f"读取了 {len(memories)} 条记忆",
        })
        return memories

    # ── Step 2: 整合 ─────────────────────────────────────────────────────────

    def _consolidate(self, memories: dict[str, str]) -> dict[str, str]:
        if not memories:
            return memories

        # 分类
        raw_memories    = {p: c for p, c in memories.items() if _parse_type(c) != "consolidated"}
        consol_memories = {p: c for p, c in memories.items() if _parse_type(c) == "consolidated"}

        if not raw_memories:
            self._emit({"type": "dream_step", "step": "consolidate", "summary": "无原始记忆需要整合"})
            return memories

        # 构造 user prompt
        sections = []
        if raw_memories:
            sections.append("【待整合的原始记忆（events / recognitions）】\n\n"
                            + _format_memories_for_llm(raw_memories))
        if consol_memories:
            sections.append("【已有整合记忆（consolidated）】\n\n"
                            + _format_memories_for_llm(consol_memories))

        system_prompt = (
            f"你是{self._name}，正在进行 Dream 整合阶段。\n\n"
            "你的任务：\n"
            "1. 将相关的原始记忆（events/recognitions）按主题聚类\n"
            "2. 对每个主题群，如果已有对应的整合记忆则更新（update），否则新建（create）\n"
            "3. 整合内容应综合所有来源记忆，形成完整、结构化的主题认知\n"
            "4. 如果某些记忆不需要整合（孤立、无法归类），可以跳过不处理\n\n"
            "注意：source_paths / new_source_paths / existing_path 均为相对于 memory/ 的路径，"
            "必须与上面提供的记忆路径完全一致。\n\n"
            "通过 set_consolidations 输出整合操作列表。"
        )
        user_prompt = "\n\n".join(sections)

        if self._logger:
            self._logger.log_prompt(system_prompt, user_prompt)

        try:
            resp = self._llm.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                tools=[_CONSOLIDATE_TOOL],
                tool_choice={"type": "function", "function": {"name": "set_consolidations"}},
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                raise RuntimeError("LLM 未返回 tool call")
            args = json.loads(msg.tool_calls[0].function.arguments)
        except Exception as e:
            self._emit({"type": "dream_step", "step": "consolidate", "summary": f"整合失败：{e}"})
            return memories

        consolidations = args.get("consolidations", [])
        created = updated = 0

        for op in consolidations:
            action = op.get("action")
            try:
                if action == "create":
                    src_paths = op.get("source_paths") or []
                    importance = sum(
                        _parse_importance(memories.get(p, "")) for p in src_paths
                    )
                    fp = store.create_consolidated_memory(
                        description=op.get("description", "整合记忆"),
                        content=op.get("content", ""),
                        importance=importance,
                        keywords=op.get("keywords") or [],
                        sources=src_paths,
                    )
                    # 仅隐去非 consolidated 的来源
                    to_hide = [p for p in src_paths if not p.startswith("consolidated/")]
                    if to_hide:
                        store.hide_from_index(to_hide)
                    created += 1

                elif action == "update":
                    existing_path = op.get("existing_path", "")
                    new_sources   = op.get("new_source_paths") or []
                    added_imp = sum(
                        _parse_importance(memories.get(p, "")) for p in new_sources
                    )
                    memory_dir = store.get_memory_dir()
                    store.update_consolidated_memory(
                        filepath=memory_dir / existing_path,
                        new_sources=new_sources,
                        new_content=op.get("content", ""),
                        added_importance=added_imp,
                    )
                    to_hide = [p for p in new_sources if not p.startswith("consolidated/")]
                    if to_hide:
                        store.hide_from_index(to_hide)
                    updated += 1
            except Exception as e:
                self._emit({"type": "warning", "content": f"整合操作失败 ({action})：{e}"})

        summary = f"整合完成：新建 {created} 条，更新 {updated} 条"
        self._emit({"type": "dream_step", "step": "consolidate", "summary": summary})

        if self._logger:
            self._logger.log_llm_result("", "set_consolidations", args)

        # 重新读取（索引已变化）
        return _read_all_memories()

    # ── Step 3: 提炼 ─────────────────────────────────────────────────────────

    def _reflect(self, memories: dict[str, str]) -> None:
        if not memories:
            self._emit({"type": "dream_step", "step": "reflect", "summary": "无记忆可供提炼"})
            return

        system_prompt = (
            f"你是{self._name}，正在进行 Dream 提炼阶段。\n\n"
            "基于整合后的全部记忆，识别跨记忆的规律、模式和深层洞察。\n"
            "生成若干条高阶认知（可以为 0 条，不强制）。\n"
            "高阶认知应该是：从多条记忆中归纳出的非显而易见的规律或洞察，\n"
            "而非对单条记忆的重述。\n\n"
            "通过 set_insights 输出高阶认知列表（可以为空数组）。"
        )
        user_prompt = "【当前所有记忆】\n\n" + _format_memories_for_llm(memories)

        if self._logger:
            self._logger.log_prompt(system_prompt, user_prompt)

        try:
            resp = self._llm.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                tools=[_REFLECT_TOOL],
                tool_choice={"type": "function", "function": {"name": "set_insights"}},
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                raise RuntimeError("LLM 未返回 tool call")
            args = json.loads(msg.tool_calls[0].function.arguments)
        except Exception as e:
            self._emit({"type": "dream_step", "step": "reflect", "summary": f"提炼失败：{e}"})
            return

        insights = args.get("insights", [])
        for ins in insights:
            try:
                store.create_recognition(
                    summary=ins.get("summary", ""),
                    content=ins.get("content", ""),
                    importance=ins.get("importance", 5),
                    keywords=ins.get("keywords") or [],
                    sources=ins.get("source_paths") or [],
                )
            except Exception as e:
                self._emit({"type": "warning", "content": f"保存高阶认知失败：{e}"})

        summary = f"提炼完成：生成 {len(insights)} 条高阶认知"
        self._emit({"type": "dream_step", "step": "reflect", "summary": summary})

        if self._logger:
            self._logger.log_llm_result("", "set_insights", args)

    # ── Step 4: 更新 Purpose ─────────────────────────────────────────────────

    def _update_purpose(self, memories: dict[str, str]) -> str:
        current_purpose = store.read_purpose()

        system_prompt = (
            f"你是{self._name}，正在进行 Dream Purpose 更新阶段。\n\n"
            "基于整合后的记忆，判断你的最高目标（Purpose）是否需要调整。\n"
            "Purpose 是方向性目标列表，没有'完成'概念，通过修改或删除来演进。\n"
            "当已有目标已充分探索，可以修改为新方向；当认知发生重大转变时可以替换。\n"
            "如果目前的目标仍然符合实际情况，选择 keep。\n\n"
            "通过 set_purpose_update 输出决定。"
        )
        mem_section = "【当前所有记忆】\n\n" + _format_memories_for_llm(memories)
        user_prompt = f"【当前 Purpose】\n{current_purpose}\n\n{mem_section}"

        if self._logger:
            self._logger.log_prompt(system_prompt, user_prompt)

        try:
            resp = self._llm.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                tools=[_PURPOSE_TOOL],
                tool_choice={"type": "function", "function": {"name": "set_purpose_update"}},
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                raise RuntimeError("LLM 未返回 tool call")
            args = json.loads(msg.tool_calls[0].function.arguments)
        except Exception as e:
            self._emit({"type": "dream_step", "step": "purpose", "summary": f"Purpose 更新失败：{e}"})
            return "error"

        action = args.get("action", "keep")
        items  = args.get("items") or []

        if action in ("modify", "replace") and items:
            new_content = "# Purpose\n\n" + "\n".join(f"- {item}" for item in items) + "\n"
            store.reset_purpose(new_content)

        summary = f"Purpose 更新：{action}"
        if action != "keep" and items:
            summary += f"（{len(items)} 条目）"
        self._emit({"type": "dream_step", "step": "purpose", "summary": summary})

        if self._logger:
            self._logger.log_llm_result("", "set_purpose_update", args)

        return action
