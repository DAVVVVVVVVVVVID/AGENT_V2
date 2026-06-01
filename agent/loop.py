"""
Loop controller — two-level autonomous loop.

Outer loop (Planner):
    read purpose → Perceive → Retrieve → generate Plan Batch → inner loop

Inner loop (Executor, per Plan):
    Perceive → Retrieve → Think (action sequence) → execute_sequence
    → on finish(): trigger shadow agent → next Plan
"""

from __future__ import annotations

import threading
from typing import Callable

from agent.dream import Dream, DreamTrigger
from agent.execute import Execute
from agent.memory import shadow, store
from agent.perceive import Perceive
from agent.personality import ocean_to_description
from agent.plan import Planner
from agent.retrieve import Retrieve
from agent.think import Think

_MAX_HISTORY = 20


# ── Default CLI emitter ───────────────────────────────────────────────────────

def _default_emit(msg: dict) -> None:
    t = msg.get("type")
    if t == "outer_start":
        print(f"\n{'═'*60}")
        print("【规划阶段】正在生成新的 Plan Batch…")
    elif t == "plan_batch":
        plans = msg["plans"]
        print(f"生成 {len(plans)} 个 Plan：")
        for i, p in enumerate(plans, 1):
            print(f"  {i}. {p}")
    elif t == "plan_start":
        print(f"\n{'─'*60}")
        print(f"【Plan {msg['plan_index']}/{msg['total']}】{msg['plan']}")
    elif t == "round_start":
        print(f"  · 第 {msg['round']} 轮")
    elif t == "thought":
        c = msg["content"]
        print(f"    思考：{c[:200]}{'…' if len(c) > 200 else ''}")
    elif t == "action_sequence":
        print(f"    行动序列（{len(msg['actions'])} 步）：")
        for a in msg["actions"]:
            args_str = ", ".join(f"{k}={v!r}" for k, v in a["arguments"].items())
            print(f"      → {a['name']}({args_str})")
    elif t == "action_result":
        for a in msg["snapshot"]:
            s = a["status"]
            name = a["name"]
            if s == "success":
                detail = str(a.get("result", ""))
                print(f"      ✓ {name}: {detail}")
            elif s == "failed":
                print(f"      ✗ {name}: {a.get('reason','')}")
            else:
                print(f"      … {name}: 未执行")
    elif t == "plan_finish":
        print(f"  ✔ Plan 完成：{msg['reply']}")
    elif t == "warning":
        print(f"  ⚠ {msg['content']}")
    elif t == "paused":
        print("⏸  已暂停，等待恢复…")
    elif t == "resumed":
        print("▶  已恢复。")


# ── Inner loop ────────────────────────────────────────────────────────────────

def _run_plan(
    plan: str,
    perceiver: Perceive,
    retriever: Retrieve,
    thinker: Think,
    executor: Execute,
    llm,
    model: str,
    emit: Callable,
    pause_flag: threading.Event | None,
    stop_flag: threading.Event | None,
    interrupt_flag: threading.Event | None,
    shared_state: dict | None,
    max_rounds: int = 30,
) -> str:
    """
    Run inner ReAct loop for a single Plan.
    Returns the finish reply when the agent calls finish().
    """
    history: list[dict] = []
    if shared_state is not None:
        shared_state["history"] = history

    round_num = 0

    while True:
        if stop_flag is not None and stop_flag.is_set():
            return ""

        if interrupt_flag is not None and interrupt_flag.is_set():
            interrupt_flag.clear()
            emit({"type": "plan_interrupted", "plan": plan})
            return "__interrupted__"

        round_num += 1
        emit({"type": "round_start", "round": round_num})

        # ── 轮次上限 ──────────────────────────────────────────────────────────
        if round_num > max_rounds:
            msg = f"Plan 已达最大轮次 {max_rounds}，强制结束。"
            emit({"type": "warning", "content": msg})
            shadow.trigger(list(history), llm, model)
            return f"[max_rounds] {msg}"

        # ── Perceive ──────────────────────────────────────────────────────────
        try:
            perceive_result = perceiver.perceive()
        except Exception as e:
            emit({"type": "warning", "content": f"Perceive 错误：{e}"})
            continue
        if shared_state is not None:
            shared_state["perceive"] = perceive_result

        # ── Chat 请求检查 ──────────────────────────────────────────────────────
        chat_result = _check_and_handle_chat(
            perceive_result=perceive_result,
            perceiver=perceiver,
            executor=executor,
            retriever=retriever,
            current_plan=plan,
            llm=llm,
            model=model,
            emit=emit,
            stop_flag=stop_flag,
            shared_state=shared_state,
        )
        if chat_result is not None:
            _handle_chat_aftermath(chat_result, llm, model, emit, shared_state)
            return "__chat_interrupted__"

        # ── Retrieve ──────────────────────────────────────────────────────────
        perceive_summary = f"位置：{perceive_result['player_state']['position']}"
        try:
            memories = retriever.retrieve(plan, perceive_summary)
        except Exception as e:
            emit({"type": "warning", "content": f"Retrieve 错误：{e}"})
            memories = []

        # ── Think ─────────────────────────────────────────────────────────────
        try:
            think_result = thinker.think(plan, history, perceive_result, memories)
        except Exception as e:
            msg = f"Think 错误：{e}"
            emit({"type": "warning", "content": msg})
            history.append({"thought": "", "action_sequence": [], "observation": msg})
            if len(history) > _MAX_HISTORY:
                history.pop(0)
            continue

        thought          = think_result["thought"]
        action_sequence  = think_result["action_sequence"]
        emit({"type": "thought",          "content": thought})
        emit({"type": "action_sequence",  "actions": action_sequence})

        # ── Execute ───────────────────────────────────────────────────────────
        try:
            snapshot = executor.execute_sequence(action_sequence)
        except Exception as e:
            msg = f"Execute 错误：{e}"
            emit({"type": "warning", "content": msg})
            history.append({"thought": thought, "action_sequence": [], "observation": msg})
            if len(history) > _MAX_HISTORY:
                history.pop(0)
            continue

        emit({"type": "action_result", "snapshot": snapshot})

        # ── 检查 send_chat_request 结果 ───────────────────────────────────────
        if shared_state is not None:
            for a in snapshot:
                if a["name"] == "send_chat_request" and a["status"] == "success":
                    shared_state["pending_request_id"] = a["result"].get("request_id")
                    break

        # ── Store history ─────────────────────────────────────────────────────
        history.append({"thought": thought, "action_sequence": snapshot})
        if len(history) > _MAX_HISTORY:
            history.pop(0)

        # ── Check finish ──────────────────────────────────────────────────────
        finish_action = next(
            (a for a in snapshot if a["name"] == "finish" and a["status"] == "success"),
            None,
        )
        if finish_action:
            reply = finish_action["result"].get("reply", "")
            emit({"type": "plan_finish", "reply": reply})
            shadow.trigger(list(history), llm, model)
            return reply

        # ── Pause checkpoint ──────────────────────────────────────────────────
        if pause_flag is not None and not pause_flag.is_set():
            emit({"type": "paused"})
            pause_flag.wait()
            emit({"type": "resumed"})


# ── Outer loop ────────────────────────────────────────────────────────────────

def run(
    perceiver: Perceive,
    retriever: Retrieve,
    planner: Planner,
    thinker: Think,
    executor: Execute,
    llm,
    model: str,
    emit: Callable[[dict], None] | None = None,
    pause_flag: threading.Event | None = None,
    stop_flag: threading.Event | None = None,
    interrupt_flag: threading.Event | None = None,
    use_file_plans_flag: threading.Event | None = None,
    shared_state: dict | None = None,
    dream_trigger: DreamTrigger | None = None,
    dreamer: Dream | None = None,
) -> None:
    """
    Run the autonomous two-level loop indefinitely.

    stop_flag: threading.Event — set() to stop after the current round.
    pause_flag: threading.Event — set=running, cleared=paused.
    shared_state: exposed keys:
        "history"      — current Plan's history list
        "perceive"     — latest perceive result
        "current_plan" — current Plan string
        "plan_batch"   — full Plan Batch list
        "plan_index"   — 1-based index of current Plan

    emit message types:
        outer_start, plan_batch, plan_start, round_start,
        thought, action_sequence, action_result,
        plan_finish, warning, paused, resumed
    """
    if emit is None:
        emit = _default_emit

    max_rounds = 30
    if shared_state is not None:
        max_rounds = shared_state.get("cfg", {}).get("loop_max_rounds", 30)
        shared_state["dream_trigger"] = dream_trigger
        shared_state["dreamer"]       = dreamer

    while True:
        if stop_flag is not None and stop_flag.is_set():
            return

        emit({"type": "outer_start"})

        # ── 手动触发标志（清除后走自动恢复逻辑）────────────────────────────
        if use_file_plans_flag is not None and use_file_plans_flag.is_set():
            use_file_plans_flag.clear()

        # ── 自动恢复：有剩余 todo Plan 则直接续执行，跳过规划────────────────
        try:
            _resume_states = store.read_plan_states()
            _resume_batch  = [s["text"] for s in _resume_states if s["status"] == "todo"]
        except Exception:
            _resume_batch = []

        if _resume_batch:
            emit({"type": "plan_batch_from_file", "plans": _resume_batch})
            if shared_state is not None:
                shared_state["plan_batch"] = _resume_batch
            for idx, plan in enumerate(_resume_batch, 1):
                if stop_flag is not None and stop_flag.is_set():
                    return
                all_states = store.read_plan_states()
                file_idx = next(
                    (i for i, s in enumerate(all_states) if s["text"] == plan and s["status"] == "todo"),
                    None,
                )
                emit({"type": "plan_start", "plan": plan, "plan_index": idx, "total": len(_resume_batch)})
                if shared_state is not None:
                    shared_state["current_plan"] = plan
                    shared_state["plan_index"]   = idx
                if file_idx is not None:
                    try:
                        store.set_plan_status(file_idx, "running")
                    except Exception:
                        pass
                reply = _run_plan(
                    plan=plan, perceiver=perceiver, retriever=retriever,
                    thinker=thinker, executor=executor, llm=llm, model=model,
                    emit=emit, pause_flag=pause_flag, stop_flag=stop_flag,
                    interrupt_flag=interrupt_flag, shared_state=shared_state,
                    max_rounds=max_rounds,
                )
                if file_idx is not None:
                    try:
                        if reply in ("__interrupted__", "__chat_interrupted__"):
                            store.set_plan_status(file_idx, "interrupted")
                        else:
                            store.set_plan_status(file_idx, "done")
                    except Exception:
                        pass
                if reply == "__chat_interrupted__":
                    emit({"type": "chat_done_replan"})
                    break
                if reply == "__interrupted__":
                    break
                if dream_trigger is not None and dreamer is not None and dream_trigger.should_dream():
                    dreamer.run()
            continue

        # ── Outer Perceive ────────────────────────────────────────────────────
        try:
            perceive_result = perceiver.perceive()
        except Exception as e:
            emit({"type": "warning", "content": f"外层 Perceive 错误：{e}"})
            continue
        if shared_state is not None:
            shared_state["perceive"] = perceive_result

        # ── Outer Retrieve ────────────────────────────────────────────────────
        purpose = store.read_purpose()
        perceive_summary = f"位置：{perceive_result['player_state']['position']}"
        try:
            memories = retriever.retrieve(purpose, perceive_summary)
        except Exception as e:
            emit({"type": "warning", "content": f"外层 Retrieve 错误：{e}"})
            memories = []

        # ── Generate Plan Batch ───────────────────────────────────────────────
        reorient_hint = ""
        if shared_state is not None:
            reorient_hint = shared_state.pop("reorient_hint", "")
        try:
            plan_batch = planner.generate(purpose, perceive_result, memories, reorient_hint=reorient_hint)
        except Exception as e:
            emit({"type": "warning", "content": f"Planner 错误：{e}"})
            continue

        emit({"type": "plan_batch", "plans": plan_batch})
        if shared_state is not None:
            shared_state["plan_batch"] = plan_batch
        try:
            store.save_plan_batch(plan_batch)
        except Exception:
            pass

        # ── Inner loop: execute each Plan ────────────────────────────────────
        for idx, plan in enumerate(plan_batch, 1):
            if stop_flag is not None and stop_flag.is_set():
                return

            emit({"type": "plan_start", "plan": plan, "plan_index": idx, "total": len(plan_batch)})
            if shared_state is not None:
                shared_state["current_plan"] = plan
                shared_state["plan_index"]   = idx

            try:
                store.set_plan_status(idx - 1, "running")
            except Exception:
                pass

            reply = _run_plan(
                plan           = plan,
                perceiver      = perceiver,
                retriever      = retriever,
                thinker        = thinker,
                executor       = executor,
                llm            = llm,
                model          = model,
                emit           = emit,
                pause_flag     = pause_flag,
                stop_flag      = stop_flag,
                interrupt_flag = interrupt_flag,
                shared_state   = shared_state,
                max_rounds     = max_rounds,
            )

            try:
                if reply in ("__interrupted__", "__chat_interrupted__"):
                    store.set_plan_status(idx - 1, "interrupted")
                else:
                    store.set_plan_status(idx - 1, "done")
            except Exception:
                pass

            if reply == "__chat_interrupted__":
                emit({"type": "chat_done_replan"})
                break
            if reply == "__interrupted__":
                break
            if dream_trigger is not None and dreamer is not None and dream_trigger.should_dream():
                dreamer.run()


# ── Chat 辅助函数 ─────────────────────────────────────────────────────────────

def _check_and_handle_chat(
    perceive_result: dict,
    perceiver: Perceive,
    executor: Execute,
    retriever: Retrieve,
    current_plan: str,
    llm,
    model: str,
    emit: Callable,
    stop_flag: threading.Event | None,
    shared_state: dict | None,
):
    """
    检查是否有待处理对话请求或当前已进入聊天室。
    返回 ChatSessionResult（已结束的对话）或 None（无需处理）。
    """
    from agent.chat_judgment import judge_chat_request, respond_to_request
    from agent.chat_session import run_chat_session

    cfg         = (shared_state or {}).get("cfg", {})
    entity_id   = perceiver._entity_id
    client      = executor._client
    agent_name  = cfg.get("name", entity_id)
    ocean       = cfg.get("ocean", {})
    personality = (
        ocean_to_description(ocean["O"], ocean["C"], ocean["E"], ocean["A"], ocean["N"])
        if ocean else ""
    )

    # ── 路径 B：自己发起，对方已接受（检测到 chat_active buff）──────────────
    buffs = perceive_result.get("player_state", {}).get("buffs", [])
    in_chat = any(
        (b["key"] if isinstance(b, dict) else b) == "chat_active"
        for b in buffs
    )
    if in_chat:
        pending_req_id = (shared_state or {}).get("pending_request_id")
        if pending_req_id:
            room_id = None
            try:
                req_status = client.get_chat_request_status(pending_req_id)
                room_id = req_status.get("chat_room_id")
                participants = req_status.get("accepted_ids", [])
                if entity_id not in participants:
                    participants = [entity_id] + participants
            except Exception as e:
                emit({"type": "warning", "content": f"查询请求状态失败：{e}"})
            if room_id:
                if shared_state is not None:
                    shared_state.pop("pending_request_id", None)
                    shared_state["current_chat_room_id"] = room_id
                return run_chat_session(
                    entity_id=entity_id, agent_name=agent_name,
                    chat_room_id=room_id, participants=participants,
                    client=client, llm=llm, model=model,
                    personality=personality, purpose=store.read_purpose(),
                    emit=emit, stop_flag=stop_flag,
                    retriever=retriever, perceiver=perceiver,
                    behavior_memories=[], partner_memories=[],
                )
        # chat_active 但没有 pending_request_id（可能是被动触发后 shared_state 已清理）
        return None

    # ── 路径 A：被动触发（对方发来请求）────────────────────────────────────
    pending = perceive_result.get("pending_chat_requests", [])
    if not pending:
        return None

    request = pending[0]   # 一次处理一个，其余下轮处理

    # 阶段一检索（无 LLM，在判断前完成）
    try:
        behavior_memories = retriever.get_recent_events(n=2, emit=emit)
    except Exception:
        behavior_memories = []
    try:
        partner_memories = retriever.get_partner_memories(request["from_name"], n=3, emit=emit)
    except Exception:
        partner_memories = []
    if not partner_memories:
        partner_memories = [f"（暂无关于 {request['from_name']} 的相关记忆）"]

    judgment = judge_chat_request(
        entity_id=entity_id,
        agent_name=agent_name,
        request=request,
        perceive_result=perceive_result,
        memories=behavior_memories + partner_memories,
        personality=personality,
        purpose=store.read_purpose(),
        current_plan=current_plan,
        llm=llm,
        model=model,
    )
    emit({
        "type":          "chat_judgment",
        "accept":        judgment.accept,
        "message":       judgment.message,
        "system_prompt": judgment.system_prompt,
        "user_prompt":   judgment.user_prompt,
        "raw_response":  judgment.raw_response,
    })

    try:
        response = respond_to_request(client, entity_id, request["request_id"], judgment)
    except Exception as e:
        emit({"type": "warning", "content": f"响应对话请求失败：{e}"})
        return None

    if not judgment.accept:
        return None

    room_id = response.get("chat_room_id")
    if not room_id:
        # 多人邀请还在等待其他人
        emit({"type": "chat_waiting", "request_id": request["request_id"]})
        return None

    participants = response.get("participants", [entity_id, request["from_entity_id"]])
    if shared_state is not None:
        shared_state["current_chat_room_id"] = room_id

    return run_chat_session(
        entity_id=entity_id, agent_name=agent_name,
        chat_room_id=room_id, participants=participants,
        client=client, llm=llm, model=model,
        personality=personality, purpose=store.read_purpose(),
        emit=emit, stop_flag=stop_flag,
        retriever=retriever, perceiver=perceiver,
        behavior_memories=behavior_memories,
        partner_memories=partner_memories,
    )


def _handle_chat_aftermath(
    chat_result,
    llm,
    model: str,
    emit: Callable,
    shared_state: dict | None,
) -> None:
    """对话结束后处理（Task 08 实现后生效）。"""
    if shared_state is not None:
        shared_state.pop("current_chat_room_id", None)
    try:
        from agent import chat_aftermath
        chat_aftermath.process(chat_result, llm, model, emit, shared_state)
    except ImportError:
        pass
    except Exception as e:
        emit({"type": "warning", "content": f"对话后处理失败：{e}"})
