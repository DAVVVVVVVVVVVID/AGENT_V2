"""
Entry point — parse args and start the ReAct loop.

Usage:
    uv run python -m agent.main --task "去沙发上休息"
    uv run python -m agent.main --task "找到书桌" --entity_id player_01
"""

from __future__ import annotations

import argparse

from agent.config import AGENT_CONFIG
from agent.sandbox_client import SandboxClient
from agent.perceive import Perceive
from agent.think import Think
from agent.execute import Execute
from agent.loop import run


def main() -> None:
    parser = argparse.ArgumentParser(description="AGENT_v1 ReAct loop")
    parser.add_argument("--task",      required=True, help="任务目标")
    parser.add_argument("--entity_id", default=AGENT_CONFIG["entity_id"], help="实体 ID")
    args = parser.parse_args()

    cfg = AGENT_CONFIG
    client   = SandboxClient(base_url="http://localhost:8000")
    perceiver = Perceive(client, vision_size=cfg["vision_size"])
    thinker   = Think(
        name=cfg["name"],
        ocean=cfg["ocean"],
        lifestyle=cfg["lifestyle"],
        common_sense=cfg.get("common_sense", []),
        llm_base_url=cfg["llm_base_url"],
        model=cfg["model"],
    )
    executor = Execute(client, entity_id=args.entity_id)

    print(f"任务：{args.task}")
    print(f"实体：{args.entity_id}")
    run(args.task, perceiver, thinker, executor)


if __name__ == "__main__":
    main()
