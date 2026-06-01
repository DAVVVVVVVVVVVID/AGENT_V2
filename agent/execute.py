"""
Execute module — executes an Action Sequence and returns a full result snapshot.

Each action in the sequence gets one of three statuses:
  "success" — executed, result recorded
  "failed"  — executed but failed, reason recorded, sequence stops
  "pending" — not reached due to earlier failure
"""

from __future__ import annotations

import httpx

from agent.sandbox_client import SandboxClient

_DIR_ZH = {"up": "上", "down": "下", "left": "左", "right": "右"}


class Execute:
    def __init__(self, client: SandboxClient, entity_id: str = "player_01"):
        self._client = client
        self._eid    = entity_id

    # ── Public API ────────────────────────────────────────────────────────────

    def execute_sequence(self, action_sequence: list[dict]) -> list[dict]:
        """
        Execute actions in order. Stop on first failure.
        Returns the full snapshot:
          [
            {"name": str, "arguments": dict, "status": "success", "result": dict},
            {"name": str, "arguments": dict, "status": "failed",  "reason": str},
            {"name": str, "arguments": dict, "status": "pending"},
            ...
          ]
        finish() is always treated as success and terminates the sequence.
        """
        snapshot: list[dict] = []
        stopped   = False

        for i, action in enumerate(action_sequence):
            name = action["name"]
            args = action.get("arguments", {})

            if stopped:
                snapshot.append({"name": name, "arguments": args, "status": "pending"})
                continue

            handler = _HANDLERS.get(name)
            if handler is None:
                snapshot.append({
                    "name":      name,
                    "arguments": args,
                    "status":    "failed",
                    "reason":    f"未知工具：{name!r}",
                })
                stopped = True
                continue

            raw = handler(self, args)

            if raw.get("is_finish"):
                snapshot.append({
                    "name":      name,
                    "arguments": args,
                    "status":    "success",
                    "result":    {"reply": raw.get("finish_reply", "")},
                })
                stopped = True   # finish terminates the sequence
                continue

            if raw["success"]:
                snapshot.append({
                    "name":      name,
                    "arguments": args,
                    "status":    "success",
                    "result":    raw["result"],
                })
            else:
                snapshot.append({
                    "name":      name,
                    "arguments": args,
                    "status":    "failed",
                    "reason":    raw["reason"],
                })
                stopped = True

        return snapshot

    # ── Info retrieval ────────────────────────────────────────────────────────

    def _get_arena_tiles(self, args: dict) -> dict:
        arena_id = args["arena_id"]
        data     = self._client.get_arena_tiles(arena_id)
        tiles    = data.get("tiles", [])
        return _ok({"tiles": tiles, "count": len(tiles)})

    def _get_object_position(self, args: dict) -> dict:
        object_id = args["object_id"]
        try:
            data = self._client.get_object_position(object_id)
            return _ok({
                "position":          data["position"],
                "tiles":             data["tiles"],
                "adjacent_walkable": data.get("adjacent_walkable", []),
            })
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return _fail(f"object '{object_id}' 不存在")
            raise

    # ── Movement ──────────────────────────────────────────────────────────────

    def _move_to_tile(self, args: dict) -> dict:
        x, y = args["x"], args["y"]
        res  = self._client.post_action(
            self._eid, "move", {"targetTile": {"x": x, "y": y}}
        )
        if res["success"]:
            r = res["result"]
            return _ok({"position": r["position"], "facing": r["facing"]})
        return _fail(_move_reason(res.get("reason", "")))

    def _move_direction(self, args: dict) -> dict:
        res = self._client.post_action(
            self._eid, "move_n",
            {"direction": args["direction"], "steps": args["steps"]},
        )
        if res["success"]:
            r = res["result"]
            return _ok({
                "position":    r["position"],
                "facing":      r["facing"],
                "steps_taken": r["steps_taken"],
            })
        return _fail(_move_reason(res.get("reason", "")))

    def _turn(self, args: dict) -> dict:
        res = self._client.post_action(
            self._eid, "turn", {"direction": args["direction"]}
        )
        return _ok({"facing": res["result"]["facing"]})

    def _move_to_area(self, args: dict) -> dict:
        res = self._client.post_action(
            self._eid, "move_to_area",
            {"area_type": args["area_type"], "area_id": args["area_id"]},
        )
        if res["success"]:
            r = res["result"]
            return _ok({"position": r["position"], "facing": r["facing"]})
        reason_map = {
            "no_walkable_tiles": f"区域 '{args['area_id']}' 内没有可行走的格子",
            "invalid_area_type": f"无效的区域类型：'{args['area_type']}'",
            "missing_area_id":   "area_id 为空",
            "move_disabled":     "当前无法移动",
        }
        return _fail(reason_map.get(res.get("reason", ""), res.get("reason", "")))

    # ── Object interaction ────────────────────────────────────────────────────

    def _use_object(self, args: dict) -> dict:
        res = self._client.post_action(self._eid, "use", {})
        if res["success"]:
            r = res["result"]
            return _ok({
                "objectId":   r.get("objectId"),
                "stateLabel": r.get("stateLabel") or r.get("playerState"),
                "message":    r.get("message"),
            })
        reason = res.get("reason", "")
        r = res.get("result") or {}
        if reason == "object_full":
            msg = r.get("message") or f"对象已满（{r.get('currentUsers')}/{r.get('maxUsers')}）"
        else:
            msg = r.get("message") or {
                "no_object_in_front": "正前方没有可使用的对象",
                "not_interactable":   "该对象不可交互",
                "use_disabled":       "当前无法使用对象",
            }.get(reason, reason)
        return _fail(msg)

    def _observe_object(self, args: dict) -> dict:
        res = self._client.post_action(self._eid, "interact", {})
        if res["success"]:
            return _ok({"message": res["result"]["message"]})
        return _fail("正前方没有可交互的对象")

    def _leave_object(self, args: dict) -> dict:
        res = self._client.post_action(self._eid, "leave", {})
        if res["success"]:
            r = res["result"]
            return _ok({"objectId": r.get("objectId")})
        return _fail("当前没有正在使用的对象")

    # ── Chat ─────────────────────────────────────────────────────────────────

    def _find_nearby_players(self, args: dict) -> dict:
        data = self._client.get_chat_nearby(self._eid)
        players = data.get("players", [])
        if not players:
            return _ok({"players": [], "message": "附近没有其他 Player"})
        desc = "、".join(f"{p['name']}（{p['entity_id']}）" for p in players)
        return _ok({"players": players, "message": f"附近有 {len(players)} 位：{desc}"})

    def _send_chat_request(self, args: dict) -> dict:
        to_ids   = args["to_entity_ids"]
        greeting = args["greeting"]
        try:
            data = self._client.post_chat_request(self._eid, to_ids, greeting)
            return _ok({
                "request_id": data["request_id"],
                "message":    f"已向 {len(to_ids)} 位发送对话邀请",
            })
        except Exception as e:
            return _fail(f"发送对话请求失败：{e}")

    # ── Recognition ──────────────────────────────────────────────────────────

    def _record_recognition(self, args: dict) -> dict:
        from agent.memory import store
        path = store.create_recognition(
            summary    = args["summary"],
            content    = args["content"],
            importance = args["importance"],
            keywords   = args.get("keywords", []),
            trigger    = args.get("trigger", ""),
        )
        return _ok({"saved": path.name, "summary": args["summary"]})

    # ── Finish ────────────────────────────────────────────────────────────────

    def _finish(self, args: dict) -> dict:
        return {
            "success":      True,
            "is_finish":    True,
            "finish_reply": args.get("reply", ""),
            "result":       {},
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ok(result: dict) -> dict:
    return {"success": True, "is_finish": False, "result": result, "reason": ""}


def _fail(reason: str) -> dict:
    return {"success": False, "is_finish": False, "result": {}, "reason": reason}


def _move_reason(code: str) -> str:
    return {
        "tile_not_walkable": "目标格子不可行走",
        "move_disabled":     "当前无法移动",
    }.get(code, code)


_HANDLERS: dict[str, callable] = {
    "get_arena_tiles":     Execute._get_arena_tiles,
    "get_object_position": Execute._get_object_position,
    "move_to_tile":        Execute._move_to_tile,
    "move_direction":      Execute._move_direction,
    "turn":                Execute._turn,
    "move_to_area":        Execute._move_to_area,
    "use_object":          Execute._use_object,
    "observe_object":      Execute._observe_object,
    "leave_object":        Execute._leave_object,
    "find_nearby_players": Execute._find_nearby_players,
    "send_chat_request":   Execute._send_chat_request,
    "record_recognition":  Execute._record_recognition,
    "finish":              Execute._finish,
}
