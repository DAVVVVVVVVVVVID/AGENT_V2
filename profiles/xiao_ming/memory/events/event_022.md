---
Description: 用户成功与床完成交互并解除占用状态
Time: 2026-05-30T12:03:21+00:00
Keywords: [床交互, use_object, 状态解除]
Type: event
Importance: 6
---

## What
用户在位置(2,3)朝向左时，对床bed_1779366945721执行use_object后解除绑定

## How
1. 确认当前格子(2,3)与床(1,3)相邻且朝向正确
2. 调用use_object触发交互
3. 通过leave_object解除占用状态

## Why
用户需要与正前方的床进行互动以完成睡眠/休息目标
