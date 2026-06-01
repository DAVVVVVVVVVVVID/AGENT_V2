---
Description: 小明在办公区成功完成desk标准化交互流程
Time: 2026-05-30T19:01:49+00:00
Keywords: [办公区, desk交互, 标准化流程, 位置验证, 任务完成]
Type: event
Importance: 8
---

## What
执行办公区desk标准化交互流程，包括获取位置、验证朝向、使用对象、结束交互及任务完成

## How
1. 通过记忆定位desk坐标(10,0)及相邻格子
2. 确认小明位置(9,0)朝向正确无需调整
3. 依次执行use_object/leave_object/finish操作
4. 流程未遇异常直接成功

## Why
遵循既定标准化流程确保交互正确性，避免方向/位置错误导致的失败

## Raw Actions
✓ use_object() → {'objectId': 'desk_1779367828152', 'stateLabel': '小明 正在使用', 'message': '开始工作吧！'}
✓ leave_object() → {'objectId': 'desk_1779367828152'}
✓ finish(reply='办公区desk标准化交互流程完成') → {'reply': '办公区desk标准化交互流程完成'}
