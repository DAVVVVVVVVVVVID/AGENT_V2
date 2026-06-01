---
Description: 测试并验证床对象交互后的状态重置流程
Time: 2026-05-30T18:45:37+00:00
Keywords: [床交互, 状态重置, 对象使用流程, 移动定位, 方向调整]
Type: event
Importance: 8
---

## What
通过获取位置、移动调整方向、使用及离开对象，完成床状态重置验证

## How
{'关键步骤': ['获取床坐标(0,3)', '移动至(0,6)', '转向上方', '使用对象触发睡眠', '离开对象恢复空闲'], '行动': ['get_object_position', 'move_to_tile', 'turn', 'use_object', 'leave_object'], '障碍': '初始位置被冰箱阻挡需调整方向'}

## Why
验证对象交互的完整状态转换流程，确保系统交互可靠性

## Raw Actions
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(x=0, y=6) → {'position': {'x': 0, 'y': 6}, 'facing': 'up'}
✓ turn(direction='up') → {'facing': 'up'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='床交互状态重置流程验证完成，已恢复idle状态') → {'reply': '床交互状态重置流程验证完成，已恢复idle状态'}
