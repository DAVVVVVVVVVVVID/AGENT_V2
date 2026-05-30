---
Description: 小明通过执行 leave_object 成功解除移动限制
Time: 2026-05-30T11:37:32+00:00
Keywords: [移动限制解除, 对象使用结束, leave_object, 状态恢复]
Type: event
Importance: 8
---

## What
目标是解除小明因使用澡堂对象导致的移动限制，通过调用 leave_object 结束使用状态并恢复 idle 状态

## How
{'关键步骤': ['调用 leave_object({}) 退出 bath_1779367293480 对象', '调用 finish() 确认任务完成'], '障碍': '无'}

## Why
当前状态限制移动，需结束对象使用以恢复行动自由
