"""
Perceive module — fetches environment + player state, computes state diff.
"""

from __future__ import annotations

from agent.sandbox_client import SandboxClient

_MONITORED = (
    "position", "facing", "state", "stateLabel",
    "hp", "energy", "buffs", "tags", "usingObjectId",
)


class Perceive:
    def __init__(self, client: SandboxClient, vision_size: int = 3):
        self._client = client
        self._vision_size = vision_size
        self._last_snapshot: dict | None = None

    def perceive(self) -> dict:
        env    = self._client.get_perceive(vision_size=self._vision_size)
        player = self._client.get_player()

        snapshot = {k: player.get(k) for k in _MONITORED}
        diff     = self._compute_diff(snapshot)
        self._last_snapshot = snapshot

        return {
            "arena_tree":   env["arena_tree"],
            "vision_tiles": env["vision_tiles"],
            "front_object": env["front_object"],
            "player_state": player,
            "state_diff":   diff,
        }

    def _compute_diff(self, current: dict) -> dict:
        if self._last_snapshot is None:
            return dict(current)
        return {
            k: current[k]
            for k in _MONITORED
            if current[k] != self._last_snapshot.get(k)
        }
