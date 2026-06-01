"""
chat_session.py — 对话循环模块（Task 06）

管理 agent 进入聊天室后的全过程：轮询消息、决定发言/等待/退出。
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from agent.think import _format_perception

_POLL_INTERVAL   = 2.0   # 秒，轮询间隔
_POST_SPEAK_WAIT = 10.0  # 秒，发言后等待对方打字的时间
_MAX_WAIT_STREAK = 10   # 连续等待次数后触发提示
_MAX_ROUNDS     = 50    # 对话最大轮次


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

        try:
            msg_dict = msg.model_dump()
        except Exception:
            msg_dict = vars(msg) if hasattr(msg, "__dict__") else str(msg)
        log = f"[第{attempt}次] content={content!r}  full_msg={msg_dict}"
        attempts_log.append(log)

        if content:
            try:
                return _parse_json(content), content
            except Exception as e:
                attempts_log[-1] += f"  解析失败: {e}"

    raise ValueError(f"{max_attempts}次尝试后仍无有效JSON\n" + "\n".join(attempts_log))

_SESSION_SYSTEM_TMPL = (
    "你是{agent_name}。\n"
    "性格：{personality}\n"
    "你的背景：{purpose}\n"
    "对话参与者：{participants_str}\n"
    "{initial_memories_section}"
    "你正在和人聊天。根据聊天记录和当前感知，以{agent_name}这个人的身份决定下一步说什么。\n"
    "就像真实的人类对话：可以回应对方，可以主动聊，可以等待，也可以结束对话。\n"
    "对方没有立刻回复时，耐心等待是正常的，也可以补充一句话或追问；只有等待时间明显过长、对话陷入僵局时，才考虑退出。\n"
    "【重要】记忆是你发言的唯一事实依据：记忆中没有记录的事情就是没有发生过的，不能凭空编造；"
    "提到具体事件时必须有记忆支撑；不记得的事直接说不记得。\n\n"
    "只输出 JSON，三种格式之一：\n"
    '  {{"action":"speak","content":"说的内容"}}\n'
    '  {{"action":"wait"}}\n'
    '  {{"action":"exit_chat","reason":"退出原因"}}'
)


@dataclass
class ChatSessionResult:
    chat_room_id: str
    participants: list[str]
    messages: list[dict] = field(default_factory=list)
    exit_reason: str = "finished"      # "finished" | "timeout" | "room_closed" | "stopped"
    duration_rounds: int = 0


def run_chat_session(
    entity_id: str,
    agent_name: str,
    chat_room_id: str,
    participants: list[str],
    client,
    llm,
    model: str,
    personality: str,
    purpose: str,
    emit: Callable[[dict], None],
    stop_flag: threading.Event | None = None,
    retriever=None,
    perceiver=None,
    behavior_memories: list[str] | None = None,
    partner_memories: list[str] | None = None,
) -> ChatSessionResult:
    """
    运行对话循环，直到退出或超时。
    阻塞调用，返回 ChatSessionResult。
    """
    all_messages: list[dict] = []
    since_seq = 0
    wait_streak = 0
    round_num = 0

    # 构建固定 system prompt（含阶段一记忆）
    participants_str = "、".join(
        f"{p}（你）" if p == entity_id else p for p in participants
    )
    initial_memories_section = ""
    if behavior_memories:
        initial_memories_section += "【近期行为记忆】\n" + "\n---\n".join(behavior_memories) + "\n\n"
    if partner_memories:
        initial_memories_section += "【对话对象相关记忆】\n" + "\n---\n".join(partner_memories) + "\n\n"
    if initial_memories_section:
        initial_memories_section = "\n" + initial_memories_section
    session_system = _SESSION_SYSTEM_TMPL.format(
        agent_name=agent_name,
        personality=personality,
        purpose=purpose,
        participants_str=participants_str,
        initial_memories_section=initial_memories_section,
    )

    emit({"type": "chat_session_start", "chat_room_id": chat_room_id})

    while True:
        # ── stop_flag 检查 ─────────────────────────────────────────────────
        if stop_flag is not None and stop_flag.is_set():
            _safe_exit(client, entity_id, chat_room_id)
            emit({"type": "chat_session_end", "exit_reason": "stopped"})
            return ChatSessionResult(
                chat_room_id=chat_room_id, participants=participants,
                messages=all_messages, exit_reason="stopped", duration_rounds=round_num,
            )

        # ── 轮次上限 ───────────────────────────────────────────────────────
        if round_num >= _MAX_ROUNDS:
            _safe_exit(client, entity_id, chat_room_id)
            emit({"type": "chat_session_end", "exit_reason": "timeout"})
            return ChatSessionResult(
                chat_room_id=chat_room_id, participants=participants,
                messages=all_messages, exit_reason="timeout", duration_rounds=round_num,
            )

        # ── 轮询聊天室 ─────────────────────────────────────────────────────
        time.sleep(_POLL_INTERVAL)

        try:
            room = client.get_chat_room(chat_room_id, entity_id, since_seq)
        except Exception as e:
            emit({"type": "chat_warning", "content": f"轮询失败：{e}"})
            round_num += 1
            continue

        if room.get("status") == "closed":
            emit({"type": "chat_session_end", "exit_reason": "room_closed"})
            return ChatSessionResult(
                chat_room_id=chat_room_id, participants=participants,
                messages=all_messages, exit_reason="room_closed", duration_rounds=round_num,
            )

        # ── 处理新消息和事件 ───────────────────────────────────────────────
        new_msgs = room.get("messages", [])
        new_evts = room.get("events", [])
        all_messages.extend(new_msgs)
        others_spoke = bool(new_msgs) and any(m["from_entity_id"] != entity_id for m in new_msgs)

        if new_msgs:
            since_seq = max(since_seq, max(m["seq"] for m in new_msgs))
            if others_spoke:
                wait_streak = 0
        if new_evts:
            since_seq = max(since_seq, max(e["seq"] for e in new_evts))
            for evt in new_evts:
                if evt["type"] == "player_exit":
                    emit({"type": "chat_event", "event": evt})

        # ── 判断是否该我发言 ────────────────────────────────────────────────
        last_sender = all_messages[-1]["from_entity_id"] if all_messages else None
        i_should_respond = (last_sender != entity_id) or (wait_streak >= _MAX_WAIT_STREAK)

        if not i_should_respond:
            wait_streak += 1
            round_num += 1
            continue

        # ── 感知 ──────────────────────────────────────────────────────────
        perceive_text = ""
        perceive_summary = ""
        if perceiver is not None:
            try:
                pr = perceiver.perceive()
                perceive_text = _format_perception(pr)
                perceive_summary = f"位置：{pr['player_state']['position']}"
            except Exception:
                pass

        # ── 阶段二：动态记忆检索（仅对方有新发言时触发）──────────────────
        round_memories: list[str] = []
        if retriever is not None and others_spoke and all_messages:
            recent_text = "\n".join(
                f"{m['from_entity_id']}: {m['content']}"
                for m in all_messages[-10:]
            )
            try:
                round_memories = retriever.retrieve_for_chat(recent_text, emit=emit)
            except Exception:
                pass

        # ── LLM 决策 ───────────────────────────────────────────────────────
        try:
            decision = _think_in_session(
                entity_id, all_messages, wait_streak, llm, model,
                session_system, perceive_text, round_memories,
            )
        except Exception as e:
            emit({"type": "chat_warning", "content": f"决策 LLM 失败：{e}"})
            wait_streak += 1
            round_num += 1
            continue

        action = decision["action"]

        if action == "speak":
            content = decision.get("content", "")
            try:
                res = client.post_chat_message(entity_id, chat_room_id, content)
                seq = res["seq"]
                all_messages.append({
                    "seq":            seq,
                    "from_entity_id": entity_id,
                    "content":        content,
                })
                since_seq = max(since_seq, seq)
                emit({
                    "type": "chat_speak", "content": content,
                    "system_prompt": decision.get("system_prompt", ""),
                    "user_prompt":   decision.get("user_prompt", ""),
                    "raw_response":  decision.get("raw_response", ""),
                })
                time.sleep(_POST_SPEAK_WAIT)
            except Exception as e:
                emit({"type": "chat_warning", "content": f"发言失败：{e}"})

        elif action == "wait":
            wait_streak += 1
            emit({
                "type": "chat_wait", "streak": wait_streak,
                "system_prompt": decision.get("system_prompt", ""),
                "user_prompt":   decision.get("user_prompt", ""),
                "raw_response":  decision.get("raw_response", ""),
            })

        elif action == "exit_chat":
            reason = decision.get("reason", "")
            emit({
                "type": "chat_exit", "reason": reason,
                "system_prompt": decision.get("system_prompt", ""),
                "user_prompt":   decision.get("user_prompt", ""),
                "raw_response":  decision.get("raw_response", ""),
            })
            _safe_exit(client, entity_id, chat_room_id)
            emit({"type": "chat_session_end", "exit_reason": "finished"})
            return ChatSessionResult(
                chat_room_id=chat_room_id, participants=participants,
                messages=all_messages, exit_reason="finished", duration_rounds=round_num,
            )

        round_num += 1


def _think_in_session(
    entity_id: str,
    all_messages: list[dict],
    wait_streak: int,
    llm,
    model: str,
    session_system: str,
    perceive_text: str,
    round_memories: list[str],
) -> dict:
    """一次 LLM 调用，返回 {"action": str, "content": str, "reason": str}"""
    neutral_hint = (
        "\n（对方已经有一段时间没有回复了，可以考虑补充一句话、追问，或者再等等看。）"
        if wait_streak >= _MAX_WAIT_STREAK else ""
    )

    history_text = "\n".join(
        f"{m['from_entity_id']}: {m['content']}" for m in all_messages[-20:]
    ) or "（对话刚开始，还没有消息）"

    user_msg = f"【对话记录】\n{history_text}{neutral_hint}"

    if perceive_text:
        user_msg += f"\n\n【当前感知】\n{perceive_text}"

    if round_memories:
        user_msg += "\n\n【当前对话相关记忆】\n" + "\n---\n".join(round_memories)

    user_msg += "\n\n请选择你的下一个行动。 /no_think"

    parsed, raw = _llm_json(
        llm, model,
        messages=[
            {"role": "system", "content": session_system},
            {"role": "user",   "content": user_msg},
        ],
    )

    action = parsed.get("action", "wait")
    meta = {"system_prompt": session_system, "user_prompt": user_msg, "raw_response": raw}
    if action == "speak":
        return {"action": "speak", "content": parsed.get("content", ""), **meta}
    elif action == "exit_chat":
        return {"action": "exit_chat", "reason": parsed.get("reason", ""), **meta}
    return {"action": "wait", **meta}


def _safe_exit(client, entity_id: str, chat_room_id: str) -> None:
    """静默退出聊天室，忽略所有异常。"""
    try:
        client.post_chat_exit(entity_id, chat_room_id)
    except Exception:
        pass
