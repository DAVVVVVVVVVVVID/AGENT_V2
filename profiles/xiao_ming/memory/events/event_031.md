---
Description: 小明成功跨区域至办公区并完成desk_1779367828152交互
Time: 2026-05-30T16:15:59+00:00
Keywords: [跨区域移动, 办公区交互, desk_1779367828152, 路径规划, 状态同步]
Type: event
Importance: 6
---

## What
从卧室(2,3)跨区域移动到办公区，经路径规划在(9,0)位点与目标desk完成交互，最终状态为成功开始工作

## How
{'使用行动': ['move_to_area', 'get_object_position', 'move_to_tile', 'turn', 'use_object', 'finish'], '关键步骤': ['move_to_area跨区域转移', 'get_object_position获取物体位置', '精准移动到相邻walkable格子', '方向调整确保交互成功率', 'use_object触发状态变换'], '障碍': '需要处理跨区域坐标系统转换，确保目标物体可见性及交互位点准确性'}

## Why
遵循event_005/event_025成熟交互流程，基于idle状态可直接跨区域的已知规则，复用成功案例event_016的路径规划方案

## Raw Actions
✓ move_to_area(area_id='workplace', area_type='arena') → {'position': {'x': 6, 'y': 3}, 'facing': 'right'}
✓ get_object_position(object_id='desk_1779367828152') → {'position': {'x': 10, 'y': 0}, 'tiles': [{'x': 10, 'y': 0}, {'x': 11, 'y': 0}], 'adjacent_walkable': [{'x': 10, 'y': 1}, {'x': 9, 'y': 0}, {'x': 11, 'y': 1}, {'x': 12, 'y': 0}]}
✓ move_to_tile(x=9, y=0) → {'position': {'x': 9, 'y': 0}, 'facing': 'up'}
✓ turn(direction='right') → {'facing': 'right'}
✓ use_object() → {'objectId': 'desk_1779367828152', 'stateLabel': '小明 正在使用', 'message': '开始工作吧！'}
✓ finish(reply='成功跨区域至办公区并完成desk交互') → {'reply': '成功跨区域至办公区并完成desk交互'}
