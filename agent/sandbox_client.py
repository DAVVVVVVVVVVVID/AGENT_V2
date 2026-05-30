"""
Sandbox API client — wraps all sandbox HTTP endpoints.
Base URL is configurable; defaults to http://localhost:8000.
"""

from __future__ import annotations

import threading
import httpx


class SandboxClient:
    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 10.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        url = f"{self._base}{path}"
        r = httpx.get(url, params=params, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self._base}{path}"
        r = httpx.post(url, json=body, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> None:
        url = f"{self._base}{path}"
        r = httpx.delete(url, timeout=self._timeout)
        r.raise_for_status()

    # ── player lifecycle ───────────────────────────────────────────────────

    def join_player(self, name: str) -> tuple[str, dict]:
        """POST /player/join — creates a player, returns (player_id, player)."""
        data = self._post("/player/join", {"name": name})
        return data["playerId"], data["player"]

    def leave_player(self, player_id: str) -> None:
        """DELETE /player/{player_id}/leave — removes the player."""
        self._delete(f"/player/{player_id}/leave")

    def start_heartbeat(self, player_id: str, interval: float = 3.0) -> threading.Event:
        """
        启动后台心跳线程，每隔 interval 秒调用 GET /player/{id}。
        返回 stop_event，调用 stop_event.set() 停止心跳。
        """
        stop_event = threading.Event()

        def _beat() -> None:
            while not stop_event.wait(interval):
                try:
                    self.get_player(player_id)
                except Exception:
                    pass

        t = threading.Thread(target=_beat, daemon=True)
        t.start()
        return stop_event

    # ── query endpoints ────────────────────────────────────────────────────

    def get_world(self) -> dict:
        """GET /world — returns tiles, objects, worldState, players."""
        return self._get("/world")

    def get_player(self, player_id: str) -> dict:
        """GET /player/{player_id} — returns full player state."""
        return self._get(f"/player/{player_id}")

    def get_events(self) -> list:
        """GET /events — returns world event list."""
        return self._get("/events")

    def get_history(self) -> list:
        """GET /history — returns action log (up to 20 entries)."""
        return self._get("/history")

    # ── agent endpoints ───────────────────────────────────────────────────

    def get_perceive(self, entity_id: str = "player_01", vision_size: int = 3) -> dict:
        """GET /agent/perceive — arena tree, vision tiles, front object."""
        return self._get("/agent/perceive", params={"entity_id": entity_id, "vision_size": vision_size})

    def get_arena_tiles(self, arena_id: str) -> dict:
        """GET /agent/arena-tiles — all tile coords in the given arena."""
        return self._get("/agent/arena-tiles", params={"arena_id": arena_id})

    def get_object_position(self, object_id: str) -> dict:
        """GET /agent/object-position — anchor position of the given object."""
        return self._get("/agent/object-position", params={"object_id": object_id})

    # ── action endpoint ────────────────────────────────────────────────────

    def post_action(
        self,
        entity_id: str,
        action_type: str,
        payload: dict | None = None,
        skip_log: bool = False,
        log_label: str | None = None,
    ) -> dict:
        """
        POST /action — unified action entry point.

        Returns a dict with at minimum:
            success (bool), type (str)
        On success also has: result (dict)
        On failure also has: reason (str)
        """
        body: dict = {
            "entityId": entity_id,
            "action": {
                "type": action_type,
                "payload": payload or {},
            },
        }
        if skip_log:
            body["skipLog"] = True
        if log_label is not None:
            body["logLabel"] = log_label
        return self._post("/action", body)
