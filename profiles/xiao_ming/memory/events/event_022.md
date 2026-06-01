---
Description: 小明成功完成从办公区跨区域到浴室并使用浴缸的多步骤交互
Time: 2026-05-30T16:02:36+00:00
Keywords: [跨区域移动, 对象使用流程, 方向校准, 多步骤交互, 状态管理]
Type: event
Importance: 9
---

## What
从办公区(9,0)离开desk对象后，经过跨区域移动、定位浴缸、调整位置和方向，最终成功使用bath_1779367293480浴缸

## How
{'key_steps': ['leave_object()解除使用状态', 'move_to_area(bathroom)区域切换', 'get_object_position获取浴缸精确坐标', '选择adjacent_walkable坐标(1,0)', 'turn(left)调整方向', 'use_object触发交互'], 'obstacles': '首轮leave后移动失败导致需要区域重连，第二步骤成功解决后衔接后续动作'}

## Why
根据event_016成功案例的验证路径，必须先解除使用状态才能跨区域移动；同时需要确保最终位置与目标对象方向对齐才能激活交互

## Raw Actions
✓ leave_object() → {'objectId': 'desk_1779367828152'}
✗ move_to_area(area_id='bathroom', area_type='arena') → 当前无法移动
✓ move_to_area(area_id='bathroom', area_type='arena') → {'position': {'x': 4, 'y': 0}, 'facing': 'left'}
✓ get_object_position(object_id='bath_1779367293480') → {'position': {'x': 0, 'y': 0}, 'tiles': [{'x': 0, 'y': 0}, {'x': 0, 'y': 1}], 'adjacent_walkable': [{'x': 1, 'y': 0}, {'x': 1, 'y': 1}]}
✓ move_to_tile(x=1, y=0) → {'position': {'x': 1, 'y': 0}, 'facing': 'left'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bath_1779367293480', 'stateLabel': '小明 正在使用', 'message': '躺进浴缸，整个人都舒畅了'}
✓ finish(reply='成功跨区域至浴室使用浴缸') → {'reply': '成功跨区域至浴室使用浴缸'}
