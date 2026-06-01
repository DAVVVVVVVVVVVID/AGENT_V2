---
Description: 床对象标准左向交互流程成功执行
Time: 2026-06-01T12:20:23+00:00
Keywords: [床交互, 位置校准, 方向调整, 对象使用]
Type: event
Importance: 8
---

## What
执行床对象标准交互流程，从(3,3)移动至(2,3)并转向左完成交互

## How
1. 通过move_to_tile移动至坐标(2,3)
2. 使用turn调整方向为左
3. 通过use_object触发床交互
4. 执行leave_object结束交互

## Why
标准交互流程需要特定位置和方向才能正确触发对象交互机制

## Raw Actions
✓ move_to_tile(y=3, x=2) → {'position': {'x': 2, 'y': 3}, 'facing': 'left'}
✓ turn(direction='left') → {'facing': 'left'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='床对象标准左向交互流程完成：(2,3)朝左成功完成交互并退出') → {'reply': '床对象标准左向交互流程完成：(2,3)朝左成功完成交互并退出'}
