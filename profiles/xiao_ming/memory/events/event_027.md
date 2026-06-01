---
Description: 小明通过解除浴缸使用状态并结束任务完成交互
Time: 2026-05-30T16:11:17+00:00
Keywords: [解除使用状态, 结束任务, leave_object, Finish, 浴缸]
Type: event
Importance: 5
---

## What
小明需要解除对浴缸的使用状态并结束任务，通过调用leave_object和finish完成流程。

## How
1. 检查当前状态后调用leave_object解除浴缸使用；2. 确认无其他限制后调用finish；3. 处理过程中发现并解除no_move和no_interact的buff限制

## Why
任务要求必须先解除使用状态才能正式结束，且Finish必须是最后一步操作，符合之前历史记录的常规流程

## Raw Actions
✓ leave_object() → {'objectId': 'bath_1779367293480'}
✓ finish(reply='成功结束浴室浴缸交互任务') → {'reply': '成功结束浴室浴缸交互任务'}
