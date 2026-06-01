---
Description: 小明跨区域移动到办公区并完成桌面交互
Time: 2026-05-30T16:08:00+00:00
Keywords: [跨区域移动, 办公区桌面, 任务流, 交互成功, 朝向调整]
Type: event
Importance: 6
---

## What
小明从卧室区域(1,8)出发，通过move_to_area切换到办公区，使用get_object_position定位desk_1779367828152位置后，经移动和转向调整，最终在(9,0)位置与桌面成功交互并完成任务

## How
{'使用工具': ['move_to_area', 'get_object_position', 'move_to_tile', 'turn', 'use_object', 'finish'], '关键步骤': ['move_to_area跨区域切换', 'get_object_position定位目标', 'move_to_tile靠近目标', 'turn调整朝向', 'use_object交互', 'finish完成任务'], '障碍': '需处理跨区域坐标转换和朝向调整'}

## Why
用户需要演示跨区域任务流的执行过程，验证卧室→办公区→桌面交互的标准操作流程

## Raw Actions
✓ move_to_area(area_type='arena', area_id='workplace') → {'position': {'x': 6, 'y': 8}, 'facing': 'right'}
✓ get_object_position(object_id='desk_1779367828152') → {'position': {'x': 10, 'y': 0}, 'tiles': [{'x': 10, 'y': 0}, {'x': 11, 'y': 0}], 'adjacent_walkable': [{'x': 10, 'y': 1}, {'x': 9, 'y': 0}, {'x': 11, 'y': 1}, {'x': 12, 'y': 0}]}
✓ move_to_tile(x=9, y=0) → {'position': {'x': 9, 'y': 0}, 'facing': 'up'}
✓ turn(direction='right') → {'facing': 'right'}
✓ use_object() → {'objectId': 'desk_1779367828152', 'stateLabel': '小明 正在使用', 'message': '开始工作吧！'}
✓ finish(reply='成功完成办公区桌面交互并结束任务') → {'reply': '成功完成办公区桌面交互并结束任务'}
