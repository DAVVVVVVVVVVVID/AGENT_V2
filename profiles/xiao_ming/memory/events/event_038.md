---
Description: 跨区域移动与办公区对象协同交互
Time: 2026-05-30T16:29:38+00:00
Keywords: [跨区域移动, 对象交互, 协同效应, 办公区导航, 方向校正]
Type: event
Importance: 8
---

## What
小明完成卧室床对象交互并跨区域至办公区成功使用办公桌，验证协同流程

## How
{'content': '1.使用卧室床对象（use_object）2.跨区域移动到办公区（move_to_area）3.获取办公桌位置（get_object_position）4.调整位置至相邻可行走格子（move_to_tile）5.修正方向至正确朝向上（turn up）6.成功交互办公桌（use_object）', 'description': '怎么做到的：关键步骤、使用哪些行动、遇到什么障碍', 'type': 'string'}

## Why
验证跨区域移动与对象交互的协同效应，为多任务规划提供验证样本

## Raw Actions
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ move_to_area(area_type='arena', area_id='workplace') → {'position': {'x': 6, 'y': 3}, 'facing': 'right'}
✓ get_object_position(object_id='desk_1779367828152') → {'position': {'x': 10, 'y': 0}, 'tiles': [{'x': 10, 'y': 0}, {'x': 11, 'y': 0}], 'adjacent_walkable': [{'x': 10, 'y': 1}, {'x': 9, 'y': 0}, {'x': 11, 'y': 1}, {'x': 12, 'y': 0}]}
✓ move_to_tile(x=4, y=5) → {'position': {'x': 4, 'y': 5}, 'facing': 'down'}
✓ turn(direction='right') → {'facing': 'right'}
✗ use_object() → 正前方没有可使用的对象
✓ move_to_tile(y=1, x=10) → {'position': {'x': 10, 'y': 1}, 'facing': 'right'}
✓ turn(direction='down') → {'facing': 'down'}
✗ use_object() → 正前方没有可使用的对象
✓ turn(direction='up') → {'facing': 'up'}
✓ use_object() → {'objectId': 'desk_1779367828152', 'stateLabel': '小明 正在使用', 'message': '开始工作吧！'}
✓ leave_object() → {'objectId': 'desk_1779367828152'}
✓ finish(reply='小明成功在办公区使用desk对象，验证跨区域移动与对象交互的协同效应') → {'reply': '小明成功在办公区使用desk对象，验证跨区域移动与对象交互的协同效应'}
