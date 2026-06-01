---
Description: 办公区desk对象方向校准边界测试：仅右向有效
Time: 2026-05-30T19:22:39+00:00
Keywords: [办公区, 方向校准, 边界测试, desk对象, 交互验证]
Type: event
Importance: 8
---

## What
测试办公区desk对象在右向时可成功交互，左、上、下方向均失败

## How
1. 移动至办公区并定位desk位置
2. 移动到相邻可行走格子(9,0)
3. 测试右向use_object成功
4. 依次测试左/上/下方向use_object均失败

## Why
验证desk对象的交互边界规则，确保系统方向校准逻辑符合预期

## Raw Actions
✓ move_to_area(area_type='arena', area_id='workplace') → {'position': {'x': 6, 'y': 3}, 'facing': 'right'}
✓ get_object_position(object_id='desk_1779367828152') → {'position': {'x': 10, 'y': 0}, 'tiles': [{'x': 10, 'y': 0}, {'x': 11, 'y': 0}], 'adjacent_walkable': [{'x': 10, 'y': 1}, {'x': 9, 'y': 0}, {'x': 11, 'y': 1}, {'x': 12, 'y': 0}]}
✓ move_to_tile(x=9, y=0) → {'position': {'x': 9, 'y': 0}, 'facing': 'up'}
✓ turn(direction='right') → {'facing': 'right'}
✓ use_object() → {'objectId': 'desk_1779367828152', 'stateLabel': '小明 正在使用', 'message': '开始工作吧！'}
✓ turn(direction='left') → {'facing': 'left'}
✗ use_object() → 正前方没有可使用的对象
✓ leave_object() → {'objectId': 'desk_1779367828152'}
✓ turn(direction='up') → {'facing': 'up'}
✗ use_object() → 当前无法使用对象
✗ use_object() → 正前方没有可使用的对象
✓ turn(direction='down') → {'facing': 'down'}
✗ use_object() → 正前方没有可使用的对象
✓ finish(reply='办公区desk方向校准边界验证完成：仅右向有效，其他方向(up/down/left)交互失败') → {'reply': '办公区desk方向校准边界验证完成：仅右向有效，其他方向(up/down/left)交互失败'}
