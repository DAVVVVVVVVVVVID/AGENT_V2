"""
Entry point — parse args and start the autonomous loop.

Usage:
    uv run python -m agent.main --profile profiles/xiao_ming
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

import openai

from agent.config import load_config
from agent.execute import Execute
from agent.logger import get_logger
from agent.loop import run
from agent.memory import store
from agent.perceive import Perceive
from agent.plan import Planner
from agent.retrieve import Retrieve
from agent.sandbox_client import SandboxClient
from agent.think import Think

log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="AGENT_v2 autonomous loop")
    parser.add_argument("--profile", required=True, help="profile 文件夹路径，例如 profiles/xiao_ming")
    args = parser.parse_args()

    profile_dir = Path(args.profile)
    if not profile_dir.exists():
        print(f"错误：profile 文件夹不存在：{profile_dir}")
        sys.exit(1)

    # ── 初始化记忆和配置 ──────────────────────────────────────────────────────
    store.init(profile_dir)
    cfg = load_config(profile_dir)

    client = SandboxClient(base_url="http://localhost:8000")

    # ── 加入沙盒 ──────────────────────────────────────────────────────────────
    try:
        player_id, _ = client.join_player(cfg["name"])
    except Exception as e:
        log.error("加入沙盒失败：%s", e)
        sys.exit(1)

    log.info("已加入沙盒，player_id=%s，名称=%s", player_id, cfg["name"])
    print(f"已加入沙盒 — player_id: {player_id}，名称: {cfg['name']}")

    heartbeat_stop = client.start_heartbeat(player_id, interval=3.0)

    # ── 优雅退出 ──────────────────────────────────────────────────────────────
    def _leave(*_):
        heartbeat_stop.set()
        try:
            client.leave_player(player_id)
            log.info("已离开沙盒，player_id=%s", player_id)
            print(f"\n已离开沙盒 — player_id: {player_id}")
        except Exception as e:
            log.warning("离开沙盒时出错：%s", e)
        sys.exit(0)

    signal.signal(signal.SIGINT,  _leave)
    signal.signal(signal.SIGTERM, _leave)

    # ── 构建组件 ──────────────────────────────────────────────────────────────
    llm   = openai.OpenAI(base_url=cfg["llm_base_url"], api_key="ollama")
    model = cfg["model"]

    perceiver = Perceive(client, entity_id=player_id, vision_size=cfg["vision_size"])
    retriever = Retrieve(llm=llm, model=model)
    planner   = Planner(name=cfg["name"], llm=llm, model=model)
    thinker   = Think(
        name=cfg["name"],
        ocean=cfg["ocean"],
        lifestyle=cfg["lifestyle"],
        common_sense=cfg.get("common_sense", []),
        llm_base_url=cfg["llm_base_url"],
        model=model,
    )
    executor = Execute(client, entity_id=player_id)

    # ── 启动循环 ──────────────────────────────────────────────────────────────
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
        heartbeat_stop.set()
        try:
            client.leave_player(player_id)
            log.info("已离开沙盒（正常退出），player_id=%s", player_id)
        except Exception:
            pass


if __name__ == "__main__":
    main()
