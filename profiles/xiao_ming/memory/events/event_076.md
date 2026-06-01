---
Description: 小明完成床对象标准位置校准流程
Time: 2026-06-01T10:27:13+00:00
Keywords: [位置校准, 床对象, 移动, 方向调整, 交互流程]
Type: event
Importance: 8
---

## What
定位床对象坐标(0,3)，移动至相邻格子(2,3)，左向交互后离开

## How
{'description': '通过get_object_position获取坐标→move_to_tile移动至相邻格子→turn左向调整方向→连续执行use_object与leave_object完成交互', 'type': 'string'}

## Why
遵循床对象交互标准流程，确保方向与位置准确性，避免此前因方向错误导致的交互失败

## Raw Actions
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(x=2, y=3) → {'position': {'x': 2, 'y': 3}, 'facing': 'up'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='床对象位置校准流程完成：定位→移动→转向左→交互→离开') → {'reply': '床对象位置校准流程完成：定位→移动→转向左→交互→离开'}
