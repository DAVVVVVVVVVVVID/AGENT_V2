---
Description: 验证卧室床对象的交互方向校准边界
Time: 2026-05-30T16:35:35+00:00
Keywords: [方向校准, 交互有效性, 卧室床, 边界测试]
Type: event
Importance: 8
---

## What
用户通过移动到卧室床的相邻格，测试不同方向的交互有效性，发现只有左向能成功使用床对象

## How
{'使用工具': ['move_to_area', 'get_object_position', 'move_to_tile', 'turn', 'use_object'], '关键步骤': ['跨区域移动至卧室', '定位床对象位置并移动到相邻格(2,3)', '左向成功交互', '依次测试右/上/下向交互均失败'], '障碍': '其他方向测试失败'}

## Why
确认方向校准对交互有效性的影响边界

## Raw Actions
✓ move_to_area(area_type='arena', area_id='bedroom') → {'position': {'x': 4, 'y': 3}, 'facing': 'left'}
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(x=2, y=3) → {'position': {'x': 2, 'y': 3}, 'facing': 'left'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ turn(direction='right') → {'facing': 'right'}
✗ use_object() → 当前无法使用对象
✓ turn(direction='up') → {'facing': 'up'}
✗ use_object() → 正前方没有可使用的对象
✓ turn(direction='down') → {'facing': 'down'}
✗ use_object() → 正前方没有可使用的对象
✓ finish(reply='床对象方向校准边界验证完成：仅当朝向左方向时可成功交互，其他方向均失败') → {'reply': '床对象方向校准边界验证完成：仅当朝向左方向时可成功交互，其他方向均失败'}
