"""
Entry point — parse args and start the autonomous loop.

Usage:
    uv run python -m agent.main
    uv run python -m agent.main --name 小红
"""

from __future__ import annotations

import argparse
import signal
import sys

from agent.config import AGENT_CONFIG
from agent.sandbox_client import SandboxClient
from agent.perceive import Perceive
from agent.think import Think
from agent.execute import Execute
from agent.plan import Planner
from agent.retrieve import Retrieve
from agent.loop import run
from agent.logger import get_logger

log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="AGENT_v2 autonomous loop")
    parser.add_argument("--name", default=AGENT_CONFIG["name"], help="玩家名称")
    args = parser.parse_args()

    cfg = AGENT_CONFIG
    client = SandboxClient(base_url="http://localhost:8000")

    # ── Join sandbox ──────────────────────────────────────────────────────────
    try:
        player_id, player_data = client.join_player(args.name)
    except Exception as e:
        log.error("加入沙盒失败：%s", e)
        sys.exit(1)

    log.info("已加入沙盒，player_id=%s，名称=%s", player_id, args.name)
    print(f"已加入沙盒 — player_id: {player_id}，名称: {args.name}")

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    def _leave(*_):
        try:
            client.leave_player(player_id)
            log.info("已离开沙盒，player_id=%s", player_id)
            print(f"\n已离开沙盒 — player_id: {player_id}")
        except Exception as e:
            log.warning("离开沙盒时出错：%s", e)
        sys.exit(0)

    signal.signal(signal.SIGINT,  _leave)
    signal.signal(signal.SIGTERM, _leave)

    # ── Build components ──────────────────────────────────────────────────────
    import openai
    llm = openai.OpenAI(base_url=cfg["llm_base_url"], api_key="ollama")
    model = cfg["model"]

    perceiver = Perceive(client, entity_id=player_id, vision_size=cfg["vision_size"])
    retriever = Retrieve(llm=llm, model=model)
    planner   = Planner(
        name=cfg["name"],
        ocean=cfg["ocean"],
        lifestyle=cfg["lifestyle"],
        common_sense=cfg.get("common_sense", []),
        llm=llm,
        model=model,
    )
    thinker = Think(
        name=cfg["name"],
        ocean=cfg["ocean"],
        lifestyle=cfg["lifestyle"],
        common_sense=cfg.get("common_sense", []),
        llm_base_url=cfg["llm_base_url"],
        model=model,
    )
    executor = Execute(client, entity_id=player_id)

    # ── Start loop ────────────────────────────────────────────────────────────
    try:
        run(
            perceiver=perceiver,
            retriever=retriever,
            planner=planner,
            thinker=thinker,
            executor=executor,
            llm=llm,
            model=model,
        )
    finally:
        try:
            client.leave_player(player_id)
            log.info("已离开沙盒（正常退出），player_id=%s", player_id)
        except Exception:
            pass


if __name__ == "__main__":
    main()
