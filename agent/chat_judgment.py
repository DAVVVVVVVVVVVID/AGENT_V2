"""
chat_judgment.py — 对话请求判断模块（Task 05）

接收到对话邀请时，做出接受/拒绝决策。
独立的轻量级 LLM 调用，与 Think 的行动规划完全解耦。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass
class JudgmentResult:
    accept: bool
    message: str          # 接受时为回应话语，拒绝时为拒绝理由
    system_prompt: str = ""
    user_prompt: str = ""
    raw_response: str = ""


def _parse_json(text: str) -> dict:
    """从 LLM 回复中提取第一个 JSON 对象。"""
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # 去掉 markdown 代码块
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


def judge_chat_request(
    entity_id: str,
    agent_name: str,
    request: dict,
    perceive_result: dict,
    memories: list[str],
    personality: str,
    purpose: str,
    current_plan: str,
    llm,
    model: str,
) -> JudgmentResult:
    """
    判断是否接受对话请求。

    request 格式：
        {"request_id": str, "from_entity_id": str, "from_name": str, "greeting": str}
    """
    memories_text = "\n".join(f"- {m}" for m in memories) if memories else "（无相关记忆）"
    position = perceive_result.get("player_state", {}).get("position", "未知")

    system = (
        f"你是{agent_name}。\n"
        f"性格：{personality}\n"
        f"你的背景：{purpose}\n\n"
        "有人向你发出对话邀请。请判断是否接受。\n"
        "接受时，message 是你说的第一句话——就像两个人相遇时自然说出的那句话，怎么自然怎么来。\n"
        "拒绝时，message 是拒绝的理由。\n"
        '只输出 JSON，格式：{"accept": true/false, "message": "回应内容"}'
    )
    user = (
        f"来自 {request['from_name']}（{request['from_entity_id']}）的对话请求：\n"
        f"\"{request['greeting']}\"\n\n"
        f"当前位置：{position}\n"
        f"相关记忆：\n{memories_text}\n\n"
        "请决定是否接受。 /no_think"
    )

    try:
        raw, raw_content = _llm_json(
            llm, model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )
        return JudgmentResult(
            accept=bool(raw.get("accept", False)),
            message=str(raw.get("message", "")).strip() or "好的",
            system_prompt=system,
            user_prompt=user,
            raw_response=raw_content,
        )
    except Exception as e:
        return JudgmentResult(
            accept=False,
            message="抱歉，现在不方便。",
            system_prompt=system,
            user_prompt=user,
            raw_response=str(e),
        )


def respond_to_request(
    client,
    entity_id: str,
    request_id: str,
    result: JudgmentResult,
) -> dict:
    """调用沙盒 /chat/respond，返回沙盒响应。"""
    return client.post_chat_respond(
        entity_id=entity_id,
        request_id=request_id,
        accept=result.accept,
        message=result.message,
    )
