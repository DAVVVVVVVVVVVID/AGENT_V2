---
Description: 成功定位并交互工作场所书桌
Time: 2026-05-30T11:39:01+00:00
Keywords: [物体定位, 路径规划, 交互操作, 工作场所, 书桌使用]
Type: event
Importance: 3
---

## What
按计划探索工作场所书桌对象，通过定位、移动、转向完成使用交互

## How
{'使用工具': ['get_object_position', 'move_to_tile', 'turn', 'use_object', 'leave_object'], '关键步骤': ['调用get_object_position获取书桌坐标', '从(6,0)移动至(12,0)相邻格子', '调整朝向为左以正对书桌', '连续执行use_object和leave_object完成交互'], '障碍': '需要路径规划穿越6格距离'}

## Why
完成预先设定的'探索并交互书桌'计划目标，属于工作场景基础功能验证
