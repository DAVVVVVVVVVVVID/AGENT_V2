"""
chat_aftermath.py — 对话后处理模块（Task 08）

对话结束后完成三步：
  1. 记忆整理：LLM 提炼 → create_chat_memory()
  2. Dream 检查：满足条件时触发 dreamer.run()
  3. 重新定向：生成 reorient_hint 写入 shared_state
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable


def _parse_json(text: str) -> dict:
    """从 LLM 回复中提取第一个 JSON 对象。"""
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    clean = re.sub(r"```(?:json)?\s*", "", clean).replace("```", "").strip()
    try:
        return json.loads(clean)
    except Exception:
        pass
    m = re.search(r"\{.*\}", clean, re.DOTALL)
    if m:
        return json.loads(m.group())
    raise ValueError(f"no JSON in: {clean!r}")


def _llm_json(llm, model: str, messages: list, max_attempts: int = 3) -> tuple[dict, str]:
    """调用 LLM 并解析 JSON，内容为空或解析失败时重试，返回 (parsed_dict, raw_content)。"""
    attempts_log: list[str] = []

    for attempt in range(1, max_attempts + 1):
        resp = llm.chat.completions.create(
            model=model,
            messages=messages,
            extra_body={"think": False},
        )
        msg = resp.choices[0].message
        content = msg.content or ""
        reasoning = getattr(msg, "reasoning_content", None) or ""

        log = f"[第{attempt}次] content={content!r}"
        if reasoning:
            log += f"  reasoning({len(reasoning)}字): {reasoning[:150]!r}"
        attempts_log.append(log)

        if content:
            try:
                return _parse_json(content), content
            except Exception as e:
                attempts_log[-1] += f"  解析失败: {e}"

    raise ValueError(f"{max_attempts}次尝试后仍无有效JSON\n" + "\n".join(attempts_log))


def process(
    chat_result,
    llm,
    model: str,
    emit: Callable[[dict], None],
    shared_state: dict | None = None,
) -> None:
    """对话结束后的三步处理。由 loop._handle_chat_aftermath 调用。"""
    emit({"type": "chat_aftermath_start"})

    _create_chat_memory(chat_result, llm, model, emit)

    # Dream 检查
    if shared_state is not None:
        dream_trigger = shared_state.get("dream_trigger")
        dreamer       = shared_state.get("dreamer")
        if dream_trigger is not None and dreamer is not None:
            try:
                if dream_trigger.should_dream():
                    emit({"type": "dream_triggered_by_chat"})
                    dreamer.run()
            except Exception as e:
                emit({"type": "warning", "content": f"Chat 后 Dream 失败：{e}"})

    _reorient(chat_result, llm, model, emit, shared_state)

    emit({"type": "chat_aftermath_done"})


# ── 步骤 1：记忆整理 ──────────────────────────────────────────────────────────

def _create_chat_memory(
    chat_result,
    llm,
    model: str,
    emit: Callable,
) -> Path | None:
    from agent.memory import store

    if not chat_result.messages:
        return None

    messages_text = "\n".join(
        f"{m['from_entity_id']}: {m['content']}"
        for m in chat_result.messages
    )

    system = (
        "你是对话记录整理助手。将以下对话整理成结构化信息。\n"
        "只输出 JSON，格式：\n"
        '{"summary":"一句话概括（15字以内）","topic":"主题内容（2-4句话）",'
        '"key_info":"对我有参考价值的关键信息，无则写\'无\'","outcome":"对话如何结束，是否影响当前计划",'
        '"keywords":["关键词1","关键词2"],"importance":整数0到10}'
    )

    raw = None
    try:
        raw, _ = _llm_json(
            llm, model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": f"对话记录：\n{messages_text} /no_think"},
            ],
        )
    except Exception as e:
        emit({"type": "warning", "content": f"记忆整理 LLM 失败：{e}"})
        raw = {
            "summary":    "一次对话",
            "topic":      messages_text[:300],
            "key_info":   "无",
            "outcome":    f"对话结束（{chat_result.exit_reason}）",
            "keywords":   [],
            "importance": 3,
        }

    try:
        path = store.create_chat_memory(
            participants=chat_result.participants,
            summary=raw["summary"],
            topic=raw["topic"],
            key_info=raw["key_info"],
            outcome=raw["outcome"],
            importance=int(raw.get("importance", 3)),
            keywords=raw.get("keywords", []),
        )
        emit({"type": "chat_memory_saved", "path": str(path)})
        return path
    except Exception as e:
        emit({"type": "warning", "content": f"保存 chat 记忆失败：{e}"})
        return None


# ── 步骤 3：重新定向 ──────────────────────────────────────────────────────────

def _reorient(
    chat_result,
    llm,
    model: str,
    emit: Callable,
    shared_state: dict | None,
) -> None:
    from agent.memory import store

    if not chat_result.messages:
        return

    purpose = store.read_purpose()
    cfg = (shared_state or {}).get("cfg", {})
    agent_name = cfg.get("name", "agent")

    messages_text = "\n".join(
        f"{m['from_entity_id']}: {m['content']}"
        for m in chat_result.messages[-10:]
    )

    system = (
        f"你是{agent_name}，刚刚完成了一段对话。\n"
        f"当前总体目标（Purpose）：{purpose}\n\n"
        "请判断对话内容是否需要调整当前目标或接下来的行动方向。\n"
        "只输出 JSON，格式：\n"
        '{"needs_reorient":true/false,"reason":"原因，不需调整写\'无\'","hint":"对下一个Plan的建议，不需调整写\'继续原计划\'"}'
    )

    try:
        raw, _ = _llm_json(
            llm, model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": f"刚才的对话：\n{messages_text} /no_think"},
            ],
        )
    except Exception as e:
        emit({"type": "warning", "content": f"重新定向 LLM 失败：{e}"})
        return

    hint = raw.get("hint", "继续原计划")
    emit({
        "type":           "chat_reorient",
        "needs_reorient": raw.get("needs_reorient", False),
        "hint":           hint,
    })

    if shared_state is not None and hint and hint != "继续原计划":
        shared_state["reorient_hint"] = hint
