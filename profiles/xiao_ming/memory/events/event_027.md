---
Description: 小明成功在卧室区域找到并使用床完成交互
Time: 2026-05-30T12:13:02+00:00
Keywords: [卧室床交互, 位置定位, 移动路径, 对象使用, 任务完成]
Type: event
Importance: 7
---

## What
定位床对象位置并移动至相邻可行走格子(2,3)，调整姿态后完成交互并解除占用

## How
{'description': '通过get_object_position获取对象位置信息，调用move_to_tile到达目标坐标，使用use_object完成交互，最后以leave_object释放资源', 'type': 'string'}

## Why
执行用户设定的移动并交互计划，获取床的休憩资源
