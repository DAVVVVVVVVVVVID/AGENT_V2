---
Description: 解除小明对浴缸的使用状态并结束任务
Time: 2026-05-30T16:18:19+00:00
Keywords: [浴缸, 解除状态, 任务结束, buff效果, 交互工具]
Type: event
Importance: 3
---

## What
小明在位置(1,0)面向左正使用浴缸bath_1779367293480，因无法移动/互动需解除状态。通过调用leave_object结束使用，继而调用finish终止任务。

## How
{'关键步骤': ['检测小明已处于浴缸相邻可行走格子', '调用leave_object({})退出使用', '调用finish()结束Plan'], '遇到的障碍': '目标对象处于无法移动和无法互动的Buff状态'}

## Why
根据工具leave_object的定义和先前成功案例（如event_017），退出使用状态是恢复闲置的必要操作。当前状态满足调用条件，无需额外移动或转向

## Raw Actions
✓ leave_object() → {'objectId': 'bath_1779367293480'}
✓ finish(reply='成功解除浴缸使用状态并结束任务') → {'reply': '成功解除浴缸使用状态并结束任务'}
