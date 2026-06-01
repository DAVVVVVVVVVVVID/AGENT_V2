---
Description: 小明跨区域移动至办公区并完成交互验证
Time: 2026-05-30T15:46:19+00:00
Keywords: [跨区域移动, 路径规划, 办公区交互, 多步骤验证]
Type: event
Importance: 8
---

## What
小明从卧室(0,7)跨区域移动至办公区(9,0)，通过路径规划在desk_1779367828152旁完成交互

## How
{'使用工具': ['move_to_area', 'get_object_position', 'use_object'], '关键步骤': ['调用move_to_area切换到workplace区域', '使用get_object_position获取桌位具体坐标', '移动到相邻可行走格子(9,0)', '调整朝向为right方向', '执行use_object完成交互'], '障碍': '跨区域坐标转换、路径规划验证'}

## Why
验证多区域环境下路径规划的正确性和连续性

## Raw Actions
✓ move_to_area(area_type='arena', area_id='workplace') → {'position': {'x': 6, 'y': 7}, 'facing': 'right'}
✓ get_object_position(object_id='desk_1779367828152') → {'position': {'x': 10, 'y': 0}, 'tiles': [{'x': 10, 'y': 0}, {'x': 11, 'y': 0}], 'adjacent_walkable': [{'x': 10, 'y': 1}, {'x': 9, 'y': 0}, {'x': 11, 'y': 1}, {'x': 12, 'y': 0}]}
✓ move_to_tile(y=0, x=9) → {'position': {'x': 9, 'y': 0}, 'facing': 'up'}
✓ turn(direction='right') → {'facing': 'right'}
✓ use_object() → {'objectId': 'desk_1779367828152', 'stateLabel': '小明 正在使用', 'message': '开始工作吧！'}
✓ finish(reply='成功验证办公区路径规划并完成交互') → {'reply': '成功验证办公区路径规划并完成交互'}
