---
Description: 小明通过跨区域移动和对象交互完成了卧室bed的使用流程
Time: 2026-05-30T16:13:32+00:00
Keywords: [区域转移, 对象交互, 路径规划, 状态管理, 卧室场景]
Type: event
Importance: 7
---

## What
从workplace区域移动至bedroom区域并成功与bed对象完成交互

## How
{'key_steps': ['调用leave_object解除desk状态', '三次尝试move_to_area区域转移', '获取目标对象邻近坐标', '调整朝向执行use_object'], 'obstacles': ['首次区域移动失败', '初始位置与目标区域不匹配', '需要三次路径调整']}

## Why
完成用户指定的卧室区域对象交互任务

## Raw Actions
✓ leave_object() → {'objectId': 'desk_1779367828152'}
✗ move_to_area(area_type='arena', area_id='bedroom') → 当前无法移动
✓ move_to_area(area_type='arena', area_id='bedroom') → {'position': {'x': 4, 'y': 3}, 'facing': 'left'}
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(x=8, y=0) → {'position': {'x': 8, 'y': 0}, 'facing': 'right'}
✓ turn(direction='right') → {'facing': 'right'}
✗ use_object() → 正前方没有可使用的对象
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(x=2, y=3) → {'position': {'x': 2, 'y': 3}, 'facing': 'left'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='成功在卧室完成bed交互并结束') → {'reply': '成功在卧室完成bed交互并结束'}
