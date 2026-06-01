---
Description: 小明成功验证卧室床对象标准交互流程，包括获取位置、移动、转向、使用及离开
Time: 2026-05-30T16:26:24+00:00
Keywords: [床交互, 位置验证, 方向调整, 标准流程]
Type: event
Importance: 6
---

## What
执行卧室床对象的完整交互验证，包含获取坐标、移动到有效位置、调整方向、触发使用及结束交互

## How
通过get_object_position获取目标床的坐标及邻近可行走格子；调用move_to_tile移动到(2,3)位置；使用turn调整方向至左侧正对床体；连续执行use_object和leave_object完成交互周期

## Why
验证标准交互流程以确保正确的位置指向和操作顺序，避免因位置误差导致的交互失败

## Raw Actions
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(x=2, y=3) → {'position': {'x': 2, 'y': 3}, 'facing': 'up'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='小明在卧室完成床对象标准交互，共消耗4步（移动1步+转向1步+交互2步）') → {'reply': '小明在卧室完成床对象标准交互，共消耗4步（移动1步+转向1步+交互2步）'}
