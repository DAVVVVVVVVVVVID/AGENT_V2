---
Description: 执行卧室冰箱标准化交互流程，成功在(0,7)朝向Down完成交互
Time: 2026-06-01T11:09:05+00:00
Keywords: [卧室交互, 坐标转换, 方向校准, 标准流程]
Type: event
Importance: 8
---

## What
小明从(2,3)移动至冰箱相邻坐标(0,7)，调整方向后完成冰箱交互，系统自动恢复状态

## How
分四阶段完成：1.通过get_object_position确认冰箱坐标(0,8)及可行走区域 2.move_to_tile移动至(0,7) 3.turn调整方向为Down 4.use_object成功触发交互, 系统自动处理leave_object需求

## Why
遵循已验证的标准流程(参考事件072)，避免方向错误导致的交互失败(参考事件039失败案例)

## Raw Actions
✓ get_object_position(object_id='fridge_1779367415680') → {'position': {'x': 0, 'y': 8}, 'tiles': [{'x': 0, 'y': 8}], 'adjacent_walkable': [{'x': 0, 'y': 7}, {'x': 1, 'y': 8}]}
✓ get_object_position(object_id='fridge_1779367415680') → {'position': {'x': 0, 'y': 8}, 'tiles': [{'x': 0, 'y': 8}], 'adjacent_walkable': [{'x': 0, 'y': 7}, {'x': 1, 'y': 8}]}
✓ move_to_tile(x=0, y=7) → {'position': {'x': 0, 'y': 7}, 'facing': 'down'}
✓ turn(direction='down') → {'facing': 'down'}
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✗ leave_object() → 当前没有正在使用的对象
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✗ leave_object() → 当前没有正在使用的对象
✗ leave_object() → 当前没有正在使用的对象
✓ finish(reply='卧室冰箱标准化交互流程完成：(0,7)朝下成功交互，系统自动恢复状态') → {'reply': '卧室冰箱标准化交互流程完成：(0,7)朝下成功交互，系统自动恢复状态'}
