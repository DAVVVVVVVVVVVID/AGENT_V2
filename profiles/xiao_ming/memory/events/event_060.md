---
Description: 执行跨区域路径优化验证(卧室→办公区)并完成交互流程
Time: 2026-05-30T19:08:40+00:00
Keywords: [跨区域路径优化, 办公区交互, 移动验证, 流程闭环, 对象定位]
Type: event
Importance: 8
---

## What
从卧室跨区域移动到办公区，定位并交互办公桌对象，验证路径优化流程

## How
使用move_to_area跨区域移动至办公区→通过get_object_position定位办公桌→move_to_tile移动到相邻格子→turn调整方向→use_object交互→完成任务

## Why
验证跨区域路径规划的可行性及交互流程的闭环性

## Raw Actions
✓ move_to_area(area_id='workplace', area_type='arena') → {'position': {'x': 6, 'y': 6}, 'facing': 'right'}
✓ get_object_position(object_id='desk_1779367828152') → {'position': {'x': 10, 'y': 0}, 'tiles': [{'x': 10, 'y': 0}, {'x': 11, 'y': 0}], 'adjacent_walkable': [{'x': 10, 'y': 1}, {'x': 9, 'y': 0}, {'x': 11, 'y': 1}, {'x': 12, 'y': 0}]}
✓ move_to_tile(x=9, y=0) → {'position': {'x': 9, 'y': 0}, 'facing': 'up'}
✓ turn(direction='right') → {'facing': 'right'}
✓ use_object() → {'objectId': 'desk_1779367828152', 'stateLabel': '小明 正在使用', 'message': '开始工作吧！'}
✓ leave_object() → {'objectId': 'desk_1779367828152'}
✓ finish(reply='跨区域路径优化验证(卧室→办公区)流程闭环验证完成') → {'reply': '跨区域路径优化验证(卧室→办公区)流程闭环验证完成'}
