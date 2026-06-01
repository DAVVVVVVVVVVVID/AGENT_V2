---
Description: 小明在卧室中成功使用床完成交互
Time: 2026-05-30T16:15:09+00:00
Keywords: [床交互, 位置确认, 成功使用, 任务完成]
Type: event
Importance: 6
---

## What
小明在坐标(2,3)朝左状态下，确认自身位于床对象(1,3)的相邻可行走格子且朝向正确，直接执行use_object后离开对象并完成任务

## How
1. 分析坐标和朝向确认无需移动
2. 调用use_object使用床对象
3. 调用leave_object结束交互
4. 通过finish完成任务流程

## Why
小明需要与床对象交互以完成休息相关的任务目标

## Raw Actions
✓ use_object() → {'objectId': 'bed_1779366945721', 'stateLabel': '小明 正在使用', 'message': '困意袭来，在床上渐渐睡去'}
✓ leave_object() → {'objectId': 'bed_1779366945721'}
✓ finish(reply='成功与卧室中的床对象交互并完成任务') → {'reply': '成功与卧室中的床对象交互并完成任务'}
