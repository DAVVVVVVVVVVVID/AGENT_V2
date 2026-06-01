---
Description: 小明成功在卧室定位并交互冰箱
Time: 2026-05-30T15:57:33+00:00
Keywords: [对象定位, 移动导航, 人机交互, 状态管理, 任务完成]
Type: event
Importance: 7
---

## What
在卧室区域通过获取对象位置、移动导航、调整朝向，最终完成冰箱交互

## How
调用get_object_position定位冰箱坐标(0,8)，通过move_to_tile移动至相邻格子(1,8)，朝向左后使用use_object触发交互，获得'好吃！'反馈并生成buff

## Why
完成用户指定的卧室冰箱交互任务，验证环境中对象操作流程的可行性

## Raw Actions
✓ get_object_position(object_id='fridge_1779367415680') → {'position': {'x': 0, 'y': 8}, 'tiles': [{'x': 0, 'y': 8}], 'adjacent_walkable': [{'x': 0, 'y': 7}, {'x': 1, 'y': 8}]}
✓ move_to_tile(x=1, y=8) → {'position': {'x': 1, 'y': 8}, 'facing': 'down'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✗ leave_object() → 当前没有正在使用的对象
✗ leave_object() → 当前没有正在使用的对象
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✗ leave_object() → 当前没有正在使用的对象
✓ finish(reply='成功在卧室定位并交互冰箱对象') → {'reply': '成功在卧室定位并交互冰箱对象'}
