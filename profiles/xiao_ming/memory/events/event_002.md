---
Description: 小明通过移动和交互成功使用了卧室中的冰箱
Time: 2026-05-30T15:36:46+00:00
Keywords: [冰箱位置获取, 路径规划, 物体交互, 方向校准, 环境探索]
Type: event
Importance: 6
---

## What
目标为冰箱功能探索，实际完成从定位到实体交互的全过程，包括位置获取、路径规划、方向调整及功能使用

## How
先调用get_object_position定位冰箱位置及周边可行走格子，再经move_to_tile移动至(1,8)，通过turn调整朝向至左侧，最终通过use_object完成交互。过程中克服了初始视角遮挡与坐标定位的障碍

## Why
响应用户关于冰箱交互的实践需求，验证空间导航与对象操作的可行性

## Raw Actions
✓ get_object_position(object_id='fridge_1779367415680') → {'position': {'x': 0, 'y': 8}, 'tiles': [{'x': 0, 'y': 8}], 'adjacent_walkable': [{'x': 0, 'y': 7}, {'x': 1, 'y': 8}]}
✓ move_to_tile(x=1, y=8) → {'position': {'x': 1, 'y': 8}, 'facing': 'down'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✓ finish(reply='成功与卧室冰箱交互并使用其功能') → {'reply': '成功与卧室冰箱交互并使用其功能'}
