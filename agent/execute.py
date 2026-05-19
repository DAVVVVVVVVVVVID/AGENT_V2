"""
Execute module — maps Think's tool call to sandbox API calls and produces Observation text.
"""

from __future__ import annotations

import httpx

from agent.sandbox_client import SandboxClient

_DIR_ZH = {"up": "上", "down": "下", "left": "左", "right": "右"}


class Execute:
    def __init__(self, client: SandboxClient, entity_id: str = "player_01"):
        self._client = client
        self._eid = entity_id

    def execute(self, tool_call: dict) -> dict:
        """
        Execute a tool call and return:
          {
            "observation":  str,
            "is_finish":    bool,
            "finish_reply": str,   # non-empty only when is_finish=True
          }
        """
        name = tool_call["name"]
        args = tool_call.get("arguments", {})
        handler = _HANDLERS.get(name)
        if handler is None:
            return _result(f"未知工具：'{name}'。")
        return handler(self, args)

    # ── info retrieval ────────────────────────────────────────────────────────

    def _get_arena_tiles(self, args: dict) -> dict:
        arena_id = args["arena_id"]
        data = self._client.get_arena_tiles(arena_id)
        n = len(data.get("tiles", []))
        return _result(f"arena '{arena_id}' 包含 {n} 个 tile。")

    def _get_object_position(self, args: dict) -> dict:
        object_id = args["object_id"]
        try:
            data = self._client.get_object_position(object_id)
            tiles    = data["tiles"]
            adjacent = data.get("adjacent_walkable", [])
            coords   = "、".join(f"({t['x']},{t['y']})" for t in tiles)
            adj_str  = "、".join(f"({t['x']},{t['y']})" for t in adjacent)
            obs = f"object '{object_id}' 占据的格子：{coords}。"
            if adj_str:
                obs += f"旁边可行走的格子：{adj_str}。"
            else:
                obs += "周围没有可行走的格子。"
            return _result(obs)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return _result(f"未找到 object '{object_id}'。")
            raise

    # ── movement ──────────────────────────────────────────────────────────────

    def _move_to_tile(self, args: dict) -> dict:
        x, y = args["x"], args["y"]
        res = self._client.post_action(
            self._eid, "move", {"targetTile": {"x": x, "y": y}}
        )
        if res["success"]:
            pos = res["result"]["position"]
            facing = _DIR_ZH.get(res["result"]["facing"], res["result"]["facing"])
            return _result(f"成功移动到 ({pos['x']}, {pos['y']})，当前朝向：{facing}。")
        reason = res.get("reason", "unknown")
        reason_zh = {
            "tile_not_walkable": "目标格子不可行走",
            "move_disabled":     "当前无法移动",
        }.get(reason, reason)
        return _result(f"尝试移动到 ({x}, {y})，失败：{reason_zh}。")

    def _move_direction(self, args: dict) -> dict:
        direction = args["direction"]
        steps = args["steps"]
        res = self._client.post_action(
            self._eid, "move_n", {"direction": direction, "steps": steps}
        )
        dir_zh = _DIR_ZH.get(direction, direction)
        if res["success"]:
            taken = res["result"]["steps_taken"]
            pos = res["result"]["position"]
            return _result(
                f"向{dir_zh}移动，实际走了 {taken} 格，到达 ({pos['x']}, {pos['y']})。"
            )
        return _result(f"尝试向{dir_zh}移动 {steps} 格，第一格即不可行走，未能移动。")

    def _turn(self, args: dict) -> dict:
        direction = args["direction"]
        self._client.post_action(self._eid, "turn", {"direction": direction})
        return _result(f"转向{_DIR_ZH.get(direction, direction)}。")

    def _move_to_area(self, args: dict) -> dict:
        area_type = args["area_type"]
        area_id = args["area_id"]
        res = self._client.post_action(
            self._eid, "move_to_area", {"area_type": area_type, "area_id": area_id}
        )
        if res["success"]:
            pos = res["result"]["position"]
            facing = _DIR_ZH.get(res["result"]["facing"], res["result"]["facing"])
            return _result(
                f"成功移动到 {area_type} '{area_id}' 内的 ({pos['x']}, {pos['y']})，朝向：{facing}。"
            )
        reason = res.get("reason", "unknown")
        reason_zh = {
            "no_walkable_tiles": f"区域 '{area_id}' 内没有可行走的格子",
            "invalid_area_type": f"无效的区域类型：'{area_type}'",
            "missing_area_id":   "area_id 为空",
            "move_disabled":     "当前无法移动",
        }.get(reason, reason)
        return _result(f"移动到 {area_type} '{area_id}' 失败：{reason_zh}。")

    # ── object interaction ────────────────────────────────────────────────────

    def _use_object(self, args: dict) -> dict:
        res = self._client.post_action(self._eid, "use", {})
        if res["success"]:
            label = res["result"].get("stateLabel") or f"正在使用 '{res['result'].get('objectId')}'。"
            return _result(label)
        reason = res.get("reason", "unknown")
        if reason == "object_full":
            r = res.get("result") or {}
            reason_zh = f"对象已满（{r.get('currentUsers')}/{r.get('maxUsers')}）"
        else:
            reason_zh = {
                "no_object_in_front": "正前方没有可使用的对象",
                "not_interactable":   "该对象不可交互",
                "use_disabled":       "当前无法使用对象",
            }.get(reason, reason)
        return _result(f"使用对象失败：{reason_zh}。")

    def _observe_object(self, args: dict) -> dict:
        res = self._client.post_action(self._eid, "interact", {})
        if res["success"]:
            return _result(f"观察正前方：{res['result']['message']}")
        return _result("正前方没有可交互的对象。")

    def _leave_object(self, args: dict) -> dict:
        res = self._client.post_action(self._eid, "leave", {})
        if res["success"]:
            obj_id = res["result"].get("objectId", "")
            return _result(f"已离开 '{obj_id}'，恢复空闲状态。")
        return _result("当前没有正在使用的对象。")

    # ── finish ────────────────────────────────────────────────────────────────

    def _finish(self, args: dict) -> dict:
        reply = args.get("reply", "")
        return {
            "observation":  "任务完成。",
            "is_finish":    True,
            "finish_reply": reply,
        }


# ── dispatch table ────────────────────────────────────────────────────────────

def _result(observation: str) -> dict:
    return {"observation": observation, "is_finish": False, "finish_reply": ""}


_HANDLERS: dict[str, callable] = {
    "get_arena_tiles":    Execute._get_arena_tiles,
    "get_object_position": Execute._get_object_position,
    "move_to_tile":       Execute._move_to_tile,
    "move_direction":     Execute._move_direction,
    "turn":               Execute._turn,
    "move_to_area":       Execute._move_to_area,
    "use_object":         Execute._use_object,
    "observe_object":     Execute._observe_object,
    "leave_object":       Execute._leave_object,
    "finish":             Execute._finish,
}
