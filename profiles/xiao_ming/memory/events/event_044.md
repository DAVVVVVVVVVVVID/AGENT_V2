---
Description: 用户成功找到并交互工作区域书桌
Time: 2026-05-30T12:40:38+00:00
Keywords: [坐标定位, 交互验证, 书桌对象, 移动路径, 方向调整]
Type: event
Importance: 7
---

## What
从坐标(6,8)定位到书桌(10,0)并完成交互验证

## How
调用get_object_position获取目标坐标→move_to_tile移动至相邻格子→turn调整朝向→use_object/leave_object完成交互→finish结束流程

## Why
验证工作环境中的书桌定位和交互流程有效性
