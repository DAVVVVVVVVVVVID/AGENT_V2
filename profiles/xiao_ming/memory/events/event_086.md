---
Description: 床对象左向标准交互流程验证及完成
Time: 2026-06-01T13:42:31+00:00
Keywords: [床交互, 位置校准, 方向调整, 流程验证, 成功完成]
Type: event
Importance: 6
---

## What
验证床对象在坐标(2,3)左向交互的完整流程，包括移动、转向、使用及退出操作

## How
{'key_steps': ['move_to_tile(2,3)定位', 'turn(left)朝向调整', 'use_object激活床功能', 'leave_object结束交互', 'finish流程收尾'], 'obstacles': '路径无障碍物，操作全程无异常'}

## Why
标准化交互验证的必要流程，确保位置/方向参数与对象响应机制的兼容性

## Raw Actions
✓ move_to_tile(x=2, y=3) → {'position': {'x': 2, 'y': 3}, 'facing': 'left'}
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='床对象标准交互流程完成：位置(2,3)左向成功使用并退出') → {'reply': '床对象标准交互流程完成：位置(2,3)左向成功使用并退出'}
