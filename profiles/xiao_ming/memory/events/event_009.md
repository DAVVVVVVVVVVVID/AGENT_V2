---
Description: 用户成功从浴室前往卧室区域并检查冰箱状态
Time: 2026-05-30T15:45:25+00:00
Keywords: [区域移动, 冰箱检查, 坐标定位, 物品交互]
Type: event
Importance: 5
---

## What
目标为检查卧室区域冰箱状态，实际执行了跨区域移动、定位冰箱、调整位置方向并完成检查

## How
{'key_steps': ['move_to_area切换区域', 'get_object_position定位冰箱坐标', 'move_to_tile移动到相邻格子', 'turn调整方向', 'use_object检查'], 'obstacles': '需要跨区域协作与坐标定位'}

## Why
确认卧室区域冰箱内物品状态是否正常

## Raw Actions
✓ move_to_area(area_type='arena', area_id='bedroom') → {'position': {'x': 2, 'y': 3}, 'facing': 'down'}
✓ get_object_position(object_id='fridge_1779367415680') → {'position': {'x': 0, 'y': 8}, 'tiles': [{'x': 0, 'y': 8}], 'adjacent_walkable': [{'x': 0, 'y': 7}, {'x': 1, 'y': 8}]}
✓ move_to_tile(y=7, x=0) → {'position': {'x': 0, 'y': 7}, 'facing': 'down'}
✓ turn(direction='down') → {'facing': 'down'}
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✓ finish(reply='已成功前往卧室区域并检查冰箱状态') → {'reply': '已成功前往卧室区域并检查冰箱状态'}
