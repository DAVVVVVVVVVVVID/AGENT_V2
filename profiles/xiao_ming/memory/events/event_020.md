---
Description: 小明通过调用finish结束任务以恢复行动自由
Time: 2026-05-30T11:59:34+00:00
Keywords: [任务完成, 状态解除, finish调用]
Type: event
Importance: 5
---

## What
小明解除书桌使用状态并结束任务

## How
第一轮调用leave_object失败后，确认状态为idle后直接调用finish结束任务

## Why
任务目标是结束书桌使用状态恢复移动自由
