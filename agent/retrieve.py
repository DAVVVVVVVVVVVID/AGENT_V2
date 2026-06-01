"""
retrieve.py — 两步 KW 检索 agent，外层/内层循环共用。

Step 1：小型 LLM 根据当前任务 + 感知摘要 + Memory.md 索引，选出 3–5 个关键词。
Step 2：在 keywords.md 反向索引中查找关联文件，按 retrieval_score 排序，取 top 5。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from agent.memory import store

# ── LLM 工具定义 ──────────────────────────────────────────────────────────────

_KW_TOOL = {
    "type": "function",
    "function": {
        "name": "select_keywords",
        "description": "选择与当前任务最相关的检索关键词",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3–5 个与当前任务/感知最相关的检索关键词",
                },
            },
            "required": ["keywords"],
        },
    },
}

_SYSTEM_PROMPT = (
    "你是一个记忆检索助手。"
    "根据当前任务和感知信息，从记忆索引中选择 3–5 个最相关的检索关键词。"
    "优先选择索引中已存在的关键词；索引中没有合适词时，可提出新关键词。"
)

_CHAT_SYSTEM_PROMPT = (
    "你是一个记忆检索助手。"
    "根据对话内容，从提供的关键词列表中选择 3–5 个最相关的检索关键词。"
    "优先关注：对话中提到的人物、地点、事件、话题。"
    "优先从提供的关键词列表中选择；列表中没有合适词时，可提出新关键词。"
)

# ── 内部工具 ──────────────────────────────────────────────────────────────────

_INDEX_RE = re.compile(r"- \[.+?\]\((.+?)\) — .+ \| (.+?) \| imp=(\d+)")


def _parse_memory_index(index_text: str) -> dict[str, tuple[float, str]]:
    """从 Memory.md 文本解析 {filepath: (importance, time_str)}。"""
    result: dict[str, tuple[float, str]] = {}
    for line in index_text.splitlines():
        m = _INDEX_RE.match(line.strip())
        if m:
            result[m.group(1)] = (float(m.group(3)), m.group(2))
    return result


def _compute_score(base_importance: float, time_str: str, matched_kw_count: int) -> float:
    """
    retrieval_score = base_importance + time_decay_bonus + kw_match_score
    time_decay_bonus = max(0, 3 - days_elapsed / 7)   # 最近 3 周内有加分
    kw_match_score   = matched_kw_count * 0.5
    """
    try:
        file_time    = datetime.fromisoformat(time_str)
        now          = datetime.now(timezone.utc)
        days_elapsed = (now - file_time).total_seconds() / 86400
    except Exception:
        days_elapsed = 0.0

    time_decay_bonus = max(0.0, 3.0 - days_elapsed / 7.0)
    kw_match_score   = matched_kw_count * 0.5
    return base_importance + time_decay_bonus + kw_match_score


# ── Retrieve 类 ───────────────────────────────────────────────────────────────

class Retrieve:
    def __init__(self, llm, model: str):
        self._llm   = llm
        self._model = model

    def retrieve(self, task_or_plan: str, perceive_summary: str, emit=None, stage: str = "initial") -> list[str]:
        """
        两步检索，返回 top-5 记忆文件正文列表。
        无记忆或检索无命中时返回空列表。
        """
        memory_index = store.load_memory_index()
        if "- [" not in memory_index:
            return []

        # ── Step 1：LLM 选关键词 ──────────────────────────────────────────────
        keywords, kw_prompt, kw_raw = self._select_keywords(task_or_plan, perceive_summary, memory_index)
        if not keywords:
            return []

        # ── Step 2：反向索引 → 候选文件 → 评分排序 → top 5 ───────────────────
        kw_index = store.get_keywords_index()       # {kw: [filepath, ...]}
        meta     = _parse_memory_index(memory_index) # {filepath: (importance, time)}

        hit_count: dict[str, int] = {}
        for kw in keywords:
            for fp in kw_index.get(kw, []):
                hit_count[fp] = hit_count.get(fp, 0) + 1

        if not hit_count:
            return []

        scored = []
        for fp, count in hit_count.items():
            if fp in meta:
                base_imp, time_str = meta[fp]
                score = _compute_score(base_imp, time_str, count)
            else:
                score = count * 0.5
            scored.append((score, fp))

        scored.sort(key=lambda x: x[0], reverse=True)
        top5_paths = [fp for _, fp in scored[:5]]
        results = store.load_files(top5_paths)

        if emit is not None:
            emit({
                "type": "chat_retrieve", "stage": stage,
                "prompt": kw_prompt, "raw": kw_raw,
                "keywords": keywords, "hits": top5_paths,
            })
        return results

    def get_recent_events(self, n: int = 2, emit=None) -> list[str]:
        """直接取最新 n 条 event 记忆，无 LLM。"""
        memory_index = store.load_memory_index()
        meta = _parse_memory_index(memory_index)
        events = [
            (time_str, fp)
            for fp, (_, time_str) in meta.items()
            if fp.startswith("events/")
        ]
        events.sort(key=lambda x: x[0], reverse=True)
        top_paths = [fp for _, fp in events[:n]]
        results = store.load_files(top_paths)
        if emit is not None:
            emit({
                "type": "chat_retrieve", "stage": "initial_behavior",
                "prompt": f"取最新 {n} 条 event 记忆",
                "raw": "", "keywords": [], "hits": top_paths,
            })
        return results

    def get_partner_memories(self, partner_name: str, n: int = 3, emit=None) -> list[str]:
        """用对方名字在 keywords 索引中查匹配文件，按 importance 取前 n 条，无 LLM。"""
        kw_index = store.get_keywords_index()
        name_lower = partner_name.lower()
        hit_files: set[str] = set()
        for kw, files in kw_index.items():
            if name_lower in kw.lower():
                hit_files.update(files)
        if not hit_files:
            if emit is not None:
                emit({
                    "type": "chat_retrieve", "stage": "initial_partner",
                    "prompt": f'按名称「{partner_name}」检索',
                    "raw": "", "keywords": [partner_name], "hits": [],
                })
            return []
        memory_index = store.load_memory_index()
        meta = _parse_memory_index(memory_index)
        scored = [
            (meta[fp][0] if fp in meta else 0.0, fp)
            for fp in hit_files
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        top_paths = [fp for _, fp in scored[:n]]
        results = store.load_files(top_paths)
        if emit is not None:
            emit({
                "type": "chat_retrieve", "stage": "initial_partner",
                "prompt": f'按名称「{partner_name}」检索',
                "raw": "", "keywords": [partner_name], "hits": top_paths,
            })
        return results

    def retrieve_for_chat(self, recent_messages_text: str, emit=None) -> list[str]:
        """
        Chat session 动态检索：基于最近对话内容选关键词，返回 top-5 记忆。
        """
        kw_index = store.get_keywords_index()
        if not kw_index:
            return []

        keywords, kw_prompt, kw_raw = self._select_keywords_chat(recent_messages_text)
        if not keywords:
            return []

        memory_index = store.load_memory_index()
        meta         = _parse_memory_index(memory_index)
        hit_count: dict[str, int] = {}
        for kw in keywords:
            for fp in kw_index.get(kw, []):
                hit_count[fp] = hit_count.get(fp, 0) + 1

        if not hit_count:
            if emit is not None:
                emit({"type": "chat_retrieve", "stage": "dynamic",
                      "prompt": kw_prompt, "raw": kw_raw,
                      "keywords": keywords, "hits": []})
            return []

        scored = []
        for fp, count in hit_count.items():
            base_imp, time_str = meta[fp] if fp in meta else (0.0, "")
            score = _compute_score(base_imp, time_str, count) if fp in meta else count * 0.5
            scored.append((score, fp))

        scored.sort(key=lambda x: x[0], reverse=True)
        top5_paths = [fp for _, fp in scored[:5]]
        results = store.load_files(top5_paths)

        if emit is not None:
            emit({"type": "chat_retrieve", "stage": "dynamic",
                  "prompt": kw_prompt, "raw": kw_raw,
                  "keywords": keywords, "hits": top5_paths})
        return results

    def _select_keywords(
        self,
        task_or_plan: str,
        perceive_summary: str,
        memory_index: str,
    ) -> tuple[list[str], str, str]:
        """返回 (keywords, user_msg, raw_arguments_str)。"""
        user_msg = (
            f"【当前任务/计划】\n{task_or_plan}\n\n"
            f"【当前感知摘要】\n{perceive_summary}\n\n"
            f"【记忆索引】\n{memory_index}"
        )
        try:
            resp = self._llm.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                tools=[_KW_TOOL],
                tool_choice={"type": "function", "function": {"name": "select_keywords"}},
            )
            tc = resp.choices[0].message.tool_calls[0]
            raw = tc.function.arguments
            keywords = json.loads(raw).get("keywords", [])
            return keywords, user_msg, raw
        except Exception:
            return [], user_msg, ""

    def _select_keywords_chat(
        self,
        recent_messages_text: str,
    ) -> tuple[list[str], str, str]:
        """返回 (keywords, user_msg, raw_arguments_str)。"""
        top_kws = store.get_top_keywords(50)
        kw_list = "、".join(top_kws) if top_kws else "（暂无关键词）"
        user_msg = (
            f"【最近对话记录】\n{recent_messages_text}\n\n"
            f"【可用关键词（共{len(top_kws)}个）】\n{kw_list}"
        )
        try:
            resp = self._llm.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _CHAT_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                tools=[_KW_TOOL],
                tool_choice={"type": "function", "function": {"name": "select_keywords"}},
            )
            tc = resp.choices[0].message.tool_calls[0]
            raw = tc.function.arguments
            keywords = json.loads(raw).get("keywords", [])
            return keywords, user_msg, raw
        except Exception:
            return [], user_msg, ""
