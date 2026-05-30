---
Description: 小明成功完成工作区域书桌的最终交互验证
Time: 2026-05-30T12:43:21+00:00
Keywords: [交互验证, 书桌, 区域移动, 对象定位, 方向调整]
Type: event
Importance: 8
---

## What
通过跨区域移动、定位书桌对象、调整方向并完成交互验证其功能属性

## How
使用move_to_area跨区域移动至workplace(6,3)，通过get_object_position确认书桌(10,0)位置后，经move_to_tile移动到(10,1)相邻格子，turn调整为up方向后use_object并leave_object

## Why
完成Plan的书桌交互验证流程以确保对象可用性
