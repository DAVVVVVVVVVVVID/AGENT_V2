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

    def retrieve(self, task_or_plan: str, perceive_summary: str) -> list[str]:
        """
        两步检索，返回 top-5 记忆文件正文列表。
        无记忆或检索无命中时返回空列表。
        """
        memory_index = store.load_memory_index()
        if "- [" not in memory_index:
            return []

        # ── Step 1：LLM 选关键词 ──────────────────────────────────────────────
        keywords = self._select_keywords(task_or_plan, perceive_summary, memory_index)
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
        return store.load_files(top5_paths)

    def _select_keywords(
        self,
        task_or_plan: str,
        perceive_summary: str,
        memory_index: str,
    ) -> list[str]:
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
            return json.loads(tc.function.arguments).get("keywords", [])
        except Exception:
            return []
