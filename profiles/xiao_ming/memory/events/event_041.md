---
Description: 成功测试跨区域移动后与卧室冰箱的连续交互流程
Time: 2026-05-30T16:38:10+00:00
Keywords: [跨区域移动, 冰箱交互, 方向校准, 对象定位, 连续性测试]
Type: event
Importance: 8
---

## What
小明通过获取冰箱坐标、移动到相邻格子并校准方向，最终完成冰箱交互

## How
通过get_object_position获取冰箱位置，使用move_to_tile到达指定格子，turn调整方向，use_object触发交互；遇到leave_object状态异常但实际已完成交互

## Why
验证跨区域移动后与目标对象的交互连续性，确保导航和对象交互流程的稳定性

## Raw Actions
✓ get_object_position(object_id='fridge_1779367415680') → {'position': {'x': 0, 'y': 8}, 'tiles': [{'x': 0, 'y': 8}], 'adjacent_walkable': [{'x': 0, 'y': 7}, {'x': 1, 'y': 8}]}
✓ get_object_position(object_id='fridge_1779367415680') → {'position': {'x': 0, 'y': 8}, 'tiles': [{'x': 0, 'y': 8}], 'adjacent_walkable': [{'x': 0, 'y': 7}, {'x': 1, 'y': 8}]}
✓ move_to_tile(x=0, y=7) → {'position': {'x': 0, 'y': 7}, 'facing': 'down'}
✓ turn(direction='down') → {'facing': 'down'}
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✗ leave_object() → 当前没有正在使用的对象
✓ finish(reply='成功测试跨区域移动后与卧室冰箱的连续交互流程（move_to_tile+精准方向校准+交互闭环）') → {'reply': '成功测试跨区域移动后与卧室冰箱的连续交互流程（move_to_tile+精准方向校准+交互闭环）'}
