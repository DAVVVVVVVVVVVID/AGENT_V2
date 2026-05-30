---
Description: 小明成功从工作区域移动至卧室区域
Time: 2026-05-30T11:40:14+00:00
Keywords: [跨区域移动, move_to_area, 卧室区域, 位置转移, 任务完成]
Type: event
Importance: 5
---

## What
执行跨区域移动任务，将小明从工作区域(12,0)位置转移到卧室区域(4,3)位置

## How
1. 分析当前区域ID和目标区域ID
2. 调用move_to_area函数指定arena类型和bedroom区域ID
3. 系统自动计算目标位置(4,3)
4. 执行完移动后调用finish确认任务完成

## Why
用户需求要求将角色从原工作区域转移到卧室区域
