---
Description: 完成从卧室到浴室的跨区域浴缸交互
Time: 2026-05-30T16:17:15+00:00
Keywords: [跨区域移动, 位置修正, 方向校准, 标准交互, 障碍处理]
Type: event
Importance: 8
---

## What
小明从卧室出发，经区域切换验证后成功移动至浴室使用浴缸

## How
确认初始状态为idle可移动->调用move_to_area跨区域->定位浴缸后移动到(1,0)格子->调整方向至正确朝向->执行use_object交互

## Why
用户需求验证跨区域标准交互流程，需确保位置调整与方向正确性

## Raw Actions
✓ leave_object() → {'objectId': 'desk_1779367828152'}
✗ move_to_area(area_id='bathroom', area_type='arena') → 当前无法移动
✓ move_to_area(area_id='bathroom', area_type='arena') → {'position': {'x': 4, 'y': 0}, 'facing': 'left'}
✓ get_object_position(object_id='bath_1779367293480') → {'position': {'x': 0, 'y': 0}, 'tiles': [{'x': 0, 'y': 0}, {'x': 0, 'y': 1}], 'adjacent_walkable': [{'x': 1, 'y': 0}, {'x': 1, 'y': 1}]}
✓ move_to_tile(x=1, y=0) → {'position': {'x': 1, 'y': 0}, 'facing': 'left'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bath_1779367293480', 'stateLabel': '小明 正在使用', 'message': '躺进浴缸，整个人都舒畅了'}
✓ finish(reply='成功从卧室出发经区域切换完成浴缸标准交互流程') → {'reply': '成功从卧室出发经区域切换完成浴缸标准交互流程'}
