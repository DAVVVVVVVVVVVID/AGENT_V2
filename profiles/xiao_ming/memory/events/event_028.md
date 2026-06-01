---
Description: 用户成功从浴室区域移动至办公区并完成desk交互验证
Time: 2026-05-30T16:12:00+00:00
Keywords: [区域移动, desk交互, 任务验证, 路径规划, 状态同步]
Type: event
Importance: 7
---

## What
目标为跨区域移动到办公区并交互验证desk，实际完成区域切换、对象定位、方向调整及成功使用desk

## How
{'使用行动': ['move_to_area', 'get_object_position', 'move_to_tile', 'turn', 'use_object'], '关键步骤': '调用move_to_area到达办公区，使用get_object_position定位desk，移动到相邻格子(9,0)，调整方向为right，执行use_object交互', '遇到障碍': '无，所有行动均一次成功'}

## Why
任务要求验证办公区desk交互流程的可行性，作为区域任务闭环的一部分

## Raw Actions
✓ move_to_area(area_type='arena', area_id='workplace') → {'position': {'x': 6, 'y': 0}, 'facing': 'right'}
✓ get_object_position(object_id='desk_1779367828152') → {'position': {'x': 10, 'y': 0}, 'tiles': [{'x': 10, 'y': 0}, {'x': 11, 'y': 0}], 'adjacent_walkable': [{'x': 10, 'y': 1}, {'x': 9, 'y': 0}, {'x': 11, 'y': 1}, {'x': 12, 'y': 0}]}
✓ move_to_tile(y=0, x=9) → {'position': {'x': 9, 'y': 0}, 'facing': 'right'}
✓ turn(direction='right') → {'facing': 'right'}
✓ use_object() → {'objectId': 'desk_1779367828152', 'stateLabel': '小明 正在使用', 'message': '开始工作吧！'}
✓ finish(reply='成功在办公区完成desk交互验证') → {'reply': '成功在办公区完成desk交互验证'}
