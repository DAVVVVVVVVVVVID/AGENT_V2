---
Description: 用户成功验证浴室跨区协同交互流程
Time: 2026-06-01T10:29:10+00:00
Keywords: [跨区协同, 交互模型, 路径调整, 方向校准, 成功验证]
Type: event
Importance: 7
---

## What
从卧室(2,3)定位至浴室(1,0)完成bath交互

## How
通过move_to_area切换区域->get_object_position获取坐标->move_to_tile调整位置->turn校准方向->use_object触发交互

## Why
测试跨区域对象交互的路径规划和协同机制

## Raw Actions
✓ move_to_area(area_id='bathroom', area_type='arena') → {'position': {'x': 2, 'y': 1}, 'facing': 'up'}
✓ get_object_position(object_id='bath_1779367293480') → {'position': {'x': 0, 'y': 0}, 'tiles': [{'x': 0, 'y': 0}, {'x': 0, 'y': 1}], 'adjacent_walkable': [{'x': 1, 'y': 0}, {'x': 1, 'y': 1}]}
✗ move_to_tile(y=2, x=3) → 目标格子不可行走
✓ get_object_position(object_id='bath_1779367293480') → {'position': {'x': 0, 'y': 0}, 'tiles': [{'x': 0, 'y': 0}, {'x': 0, 'y': 1}], 'adjacent_walkable': [{'x': 1, 'y': 0}, {'x': 1, 'y': 1}]}
✓ move_to_tile(x=1, y=0) → {'position': {'x': 1, 'y': 0}, 'facing': 'up'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bath_1779367293480', 'stateLabel': '小明 正在使用', 'message': '躺进浴缸，整个人都舒畅了'}
✓ finish(reply='浴室bath跨区协同交互验证成功：从(2,1)调整到相邻格(1,0)朝左方向完成交互') → {'reply': '浴室bath跨区协同交互验证成功：从(2,1)调整到相邻格(1,0)朝左方向完成交互'}
