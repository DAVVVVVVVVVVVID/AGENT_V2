---
Description: 测试卧室床对象标准交互流程完整性
Time: 2026-05-30T19:06:33+00:00
Keywords: [床对象, 交互流程, 移动定位, 方向调整, 标准验证]
Type: event
Importance: 7
---

## What
验证床对象交互全流程：定位→移动→转向→使用→离开

## How
{'description': '1.调用get_object_position获取床坐标(0,3)及可行走格子 2.使用move_to_tile移动到(0,6) 3.通过turn工具调整方向 4.执行use_object和leave_object交互', 'type': 'string'}

## Why
确保虚拟环境中床的标准交互流程符合设计规范，为后续测试建立基准

## Raw Actions
✓ get_object_position(object_id='bed_1779366945721') → {'position': {'x': 0, 'y': 3}, 'tiles': [{'x': 0, 'y': 3}, {'x': 1, 'y': 3}, {'x': 0, 'y': 4}, {'x': 1, 'y': 4}, {'x': 0, 'y': 5}, {'x': 1, 'y': 5}], 'adjacent_walkable': [{'x': 2, 'y': 3}, {'x': 2, 'y': 4}, {'x': 0, 'y': 6}, {'x': 1, 'y': 6}, {'x': 2, 'y': 5}]}
✓ move_to_tile(y=6, x=0) → {'position': {'x': 0, 'y': 6}, 'facing': 'up'}
✓ turn(direction='up') → {'facing': 'up'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='成功执行卧室床对象标准交互全流程：获取位置→移动→转向→使用→离开') → {'reply': '成功执行卧室床对象标准交互全流程：获取位置→移动→转向→使用→离开'}
