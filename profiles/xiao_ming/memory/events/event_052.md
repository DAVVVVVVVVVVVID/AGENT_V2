---
Description: 成功验证床对象交互流程及方向校准稳定性
Time: 2026-05-30T18:58:08+00:00
Keywords: [床交互验证, 方向校准, 移动步骤, 可靠流程, 对象ID_1779366945721]
Type: event
Importance: 7
---

## What
通过标准流程验证床对象(1779366945721)的交互可靠性，包含位置获取、移动、方向校准和交互执行

## How
调用get_object_position获取床位置(0,3)，移动至(2,5)可行走格子，左转校准方向后执行use_object和leave_object

## Why
确保床对象的基础交互流程符合标准操作规范，验证方向校准是否避免误操作

## Raw Actions
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(x=2, y=5) → {'position': {'x': 2, 'y': 5}, 'facing': 'up'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='床对象交互流程验证完成，方向校准稳定可靠') → {'reply': '床对象交互流程验证完成，方向校准稳定可靠'}
