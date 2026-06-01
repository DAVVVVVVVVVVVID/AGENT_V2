---
Description: 完成床对象左向交互流程
Time: 2026-06-01T11:14:51+00:00
Keywords: [床交互, 移动导航, 成功交互, 标准流程, 方向控制]
Type: event
Importance: 7
---

## What
用户通过定位床对象并按照标准流程完成左向交互，包括移动、转向和使用动作

## How
1.获取床对象精确位置及周边可行走格子 2.执行move_to_tile到(2,3) 3.调整左向姿态 4.连续执行use_object和leave_object 5.系统自动状态恢复

## Why
卧室场景中需要按照标准化交互流程处理床对象操作

## Raw Actions
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(x=2, y=3) → {'position': {'x': 2, 'y': 3}, 'facing': 'left'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='床对象标准左向交互流程完成：(2,3)朝左成功交互，系统自动恢复状态') → {'reply': '床对象标准左向交互流程完成：(2,3)朝左成功交互，系统自动恢复状态'}
