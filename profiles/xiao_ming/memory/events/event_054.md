---
Description: 卧室-办公区跨区域路径交互时序优化验证
Time: 2026-05-30T19:00:39+00:00
Keywords: [跨区域路径, 交互时序, 流程验证, 办公区, 卧室]
Type: event
Importance: 7
---

## What
验证卧室与办公区跨区域移动和交互的时序效率，完成全链路流程测试

## How
1.执行move_to_area跨区域到办公区；2.调用get_object_position定位办公桌；3.移动到相邻格子；4.调整方向；5.连续执行use和leave交互；6.完成路径验证。全程使用标准交互流程且未出现阻塞

## Why
基于house区域分层结构优化交互时序，确保多场所间操作符合预期设计，为后续路径优化提供基准数据

## Raw Actions
✓ move_to_area(area_type='arena', area_id='workplace') → {'position': {'x': 6, 'y': 1}, 'facing': 'right'}
✓ get_object_position(object_id='desk_1779367828152') → {'position': {'x': 10, 'y': 0}, 'tiles': [{'x': 10, 'y': 0}, {'x': 11, 'y': 0}], 'adjacent_walkable': [{'x': 10, 'y': 1}, {'x': 9, 'y': 0}, {'x': 11, 'y': 1}, {'x': 12, 'y': 0}]}
✓ move_to_tile(x=9, y=0) → {'position': {'x': 9, 'y': 0}, 'facing': 'right'}
✓ turn(direction='right') → {'facing': 'right'}
✓ use_object() → {'objectId': 'desk_1779367828152', 'stateLabel': '小明 正在使用', 'message': '开始工作吧！'}
✓ leave_object() → {'objectId': 'desk_1779367828152'}
✓ finish(reply='卧室-办公区跨区域路径交互优化验证完成，时序流程符合标准') → {'reply': '卧室-办公区跨区域路径交互优化验证完成，时序流程符合标准'}
