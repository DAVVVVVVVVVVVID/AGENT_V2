---
Description: 执行卧室环境中的床对象交互任务
Time: 2026-05-30T15:35:40+00:00
Keywords: [环境交互, 对象使用, 坐标导航, 任务完成]
Type: event
Importance: 5
---

## What
用户从(3,3)位置通过获取坐标并移动至相邻格子(2,3)，调整方向后成功完成床对象的交互并离开

## How
1. 使用get_object_position获取床对象坐标(0,3)及相邻可行走区域
2. 通过move_to_tile移动至(2,3)位置
3. 调整方向至左侧面向床对象
4. 连续执行use_object和leave_object完成交互过程

## Why
完成预设的卧室环境交互测试任务，验证对象使用流程的完整性

## Raw Actions
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(x=2, y=3) → {'position': {'x': 2, 'y': 3}, 'facing': 'left'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='成功与床交互并离开') → {'reply': '成功与床交互并离开'}
