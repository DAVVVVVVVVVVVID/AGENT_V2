---
Description: 小明成功跨区域至浴室使用浴缸
Time: 2026-05-30T16:10:19+00:00
Keywords: [跨区域移动, 对象交互, 路径规划, 状态管理]
Type: event
Importance: 7
---

## What
小明在办公区使用desk后需跨区域到bathroom使用bath_1779367293480，需完成状态解除、区域移动、位置定位和交互动作

## How
1. 通过leave_object解除desk使用状态；2. 多次尝试move_to_area(bathroom)直到区域移动成功；3. 使用get_object_position获取浴缸坐标及相邻可行走格子；4. 移动至(1,0)位置并左转调整朝向；5. 执行use_object完成浴缸交互。障碍包括首轮move_to_area失败和路径规划误差

## Why
需遵循场景规则：跨区域移动前必须解除当前区域交互状态，且对象交互需满足位置和朝向要求

## Raw Actions
✓ leave_object() → {'objectId': 'desk_1779367828152'}
✗ move_to_area(area_type='arena', area_id='bathroom') → 当前无法移动
✗ leave_object() → 当前没有正在使用的对象
✓ move_to_area(area_type='arena', area_id='bathroom') → {'position': {'x': 4, 'y': 0}, 'facing': 'left'}
✓ get_object_position(object_id='bath_1779367293480') → {'position': {'x': 0, 'y': 0}, 'tiles': [{'x': 0, 'y': 0}, {'x': 0, 'y': 1}], 'adjacent_walkable': [{'x': 1, 'y': 0}, {'x': 1, 'y': 1}]}
✓ move_to_tile(x=1, y=0) → {'position': {'x': 1, 'y': 0}, 'facing': 'left'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bath_1779367293480', 'stateLabel': '小明 正在使用', 'message': '躺进浴缸，整个人都舒畅了'}
✓ finish(reply='成功跨区域至浴室使用浴缸') → {'reply': '成功跨区域至浴室使用浴缸'}
