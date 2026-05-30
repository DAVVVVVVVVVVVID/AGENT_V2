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
from agent.plan import Planner
from agent.retrieve import Retrieve
from agent.think import Think

_MAX_HISTORY = 10


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

        # ── Perceive ──────────────────────────────────────────────────────────
        try:
            perceive_result = perceiver.perceive()
        except Exception as e:
            emit({"type": "warning", "content": f"Perceive 错误：{e}"})
            continue
        if shared_state is not None:
            shared_state["perceive"] = perceive_result

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

    while True:
        if stop_flag is not None and stop_flag.is_set():
            return

        emit({"type": "outer_start"})

        # ── 检查是否使用文件中的 Plan（跳过规划）────────────────────────────
        if use_file_plans_flag is not None and use_file_plans_flag.is_set():
            use_file_plans_flag.clear()
            try:
                states = store.read_plan_states()
                plan_batch = [s["text"] for s in states if s["status"] == "todo"]
            except Exception as e:
                emit({"type": "warning", "content": f"读取文件 Plan 错误：{e}"})
                plan_batch = []
            if not plan_batch:
                emit({"type": "warning", "content": "文件中无待执行 Plan，重新规划。"})
                # 降级为正常规划
                use_file_plans_flag = None  # 不再重试，走下面的正常路径
            else:
                emit({"type": "plan_batch_from_file", "plans": plan_batch})
                if shared_state is not None:
                    shared_state["plan_batch"] = plan_batch
                # 不调用 save_plan_batch，保留文件原有状态
                for idx, plan in enumerate(plan_batch, 1):
                    if stop_flag is not None and stop_flag.is_set():
                        return
                    # 找到该 plan 在文件中的真实 index（跳过已 done/interrupted 的）
                    all_states = store.read_plan_states()
                    file_idx = next(
                        (i for i, s in enumerate(all_states) if s["text"] == plan and s["status"] == "todo"),
                        None,
                    )
                    emit({"type": "plan_start", "plan": plan, "plan_index": idx, "total": len(plan_batch)})
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
                    )
                    if file_idx is not None:
                        try:
                            if reply == "__interrupted__":
                                store.set_plan_status(file_idx, "interrupted")
                            else:
                                store.set_plan_status(file_idx, "done")
                        except Exception:
                            pass
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
        try:
            plan_batch = planner.generate(purpose, perceive_result, memories)
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
            )

            try:
                if reply == "__interrupted__":
                    store.set_plan_status(idx - 1, "interrupted")
                    break
                else:
                    store.set_plan_status(idx - 1, "done")
            except Exception:
                pass

            if dream_trigger is not None and dreamer is not None and dream_trigger.should_dream():
                dreamer.run()
