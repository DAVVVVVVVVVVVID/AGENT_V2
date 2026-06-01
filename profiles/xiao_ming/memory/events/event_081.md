---
Description: 验证了卧室床对象左向交互的完整闭环流程
Time: 2026-06-01T11:06:08+00:00
Keywords: [床交互, 左向流程, 闭环验证, 对象定位, 状态重置]
Type: event
Importance: 8
---

## What
通过获取床位置→移动到邻近坐标(2,3)→左向对准→成功使用并离开床对象，完成交互状态重置

## How
依次执行get_object_position获取坐标, move_to_tile定位到(2,3), turn调整朝向, use_object/leave_object完成交互闭环

## Why
用于验证床对象在特定朝向下的完整交互逻辑，确保游戏系统中对象交互的稳定性和方向性规则

## Raw Actions
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(x=2, y=3) → {'position': {'x': 2, 'y': 3}, 'facing': 'left'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='床对象左向交互闭环流程验证完成：通过(2,3)左向成功交互并重置状态') → {'reply': '床对象左向交互闭环流程验证完成：通过(2,3)左向成功交互并重置状态'}
