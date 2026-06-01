---
Description: 用户完成办公桌交互并结束任务
Time: 2026-05-30T15:46:57+00:00
Keywords: [办公桌交互终止, user_state更新, finish()调用, leave_object, 任务生命周期管理]
Type: event
Importance: 6
---

## What
在办公桌(9,0)位置结束using状态并执行finish()终止任务

## How
调用leave_object解除办公桌占用后，通过finish()确认任务完成。步骤与历史记忆中的交互终止流程一致，无异常障碍

## Why
需要按交互对象的结束流程退出占用状态，符合记忆中event_006记录的办公桌使用规范和任务终止机制

## Raw Actions
✓ leave_object() → {'objectId': 'desk_1779367828152'}
✓ finish(reply='成功完成办公桌交互任务并结束') → {'reply': '成功完成办公桌交互任务并结束'}
