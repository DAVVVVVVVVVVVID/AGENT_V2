---
Description: 床对象交互流程：位置校准(2,3)左向成功使用
Time: 2026-06-01T10:40:07+00:00
Keywords: [床对象交互, 方向校准, 位置移动, 成功使用, 流程优化]
Type: event
Importance: 8
---

## What
小明完成床对象标准交互流程，通过位置校准和方向调整成功交互

## How
1.调用get_object_position获取床坐标(0,3)及相邻可行走格子
2.移动到(2,3)坐标点
3.执行turn(left)调整朝向
4.使用use_object完成交互
5.通过leave_object结束流程

## Why
根据事件039失败案例验证，床对象必须左向才能成功交互，需严格校准方向

## Raw Actions
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(x=2, y=3) → {'position': {'x': 2, 'y': 3}, 'facing': 'left'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='床对象标准交互流程完成：位置校准(2,3)左向成功使用对象') → {'reply': '床对象标准交互流程完成：位置校准(2,3)左向成功使用对象'}
