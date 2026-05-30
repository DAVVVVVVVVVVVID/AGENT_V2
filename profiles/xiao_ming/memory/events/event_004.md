---
Description: 用户通过移动和转向与洗澡间浴缸对象完成交互
Time: 2026-05-30T11:36:36+00:00
Keywords: [洗澡间, 浴缸交互, 网格移动, 方向调整, 任务完成]
Type: event
Importance: 5
---

## What
目标为探索洗澡间浴缸(bath_1779367293480)，完成移动至相邻位置、调整方向并触发使用对象交互

## How
调用get_object_position获取位置信息→执行move_to_tile(1,0)到达相邻格子→通过turn(left)调整朝向→使用use_object发起交互→最终finish任务

## Why
根据任务需求需要与指定区域的浴缸进行直接交互以完成探索
