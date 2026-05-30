---
Description: 用户通过移动和转向完成卧室床对象的探索交互
Time: 2026-05-30T11:33:35+00:00
Keywords: [探索床对象, 移动路径规划, 方向调整, 物品交互, 卧室场景]
Type: event
Importance: 5
---

## What
目标是探索卧室床对象，实际通过移动到相邻格子并调整方向后成功使用床对象

## How
{'key_steps': ['调用get_object_position获取床的坐标和相邻可行走区域', '执行move_to_tile(2,3)移动到目标位置', "调用turn('left')调整朝向", '通过use_object完成床的交互使用', '调用finish()结束任务'], 'obstacles': '需要处理坐标定位和方向调整的先后顺序'}

## Why
用户处于卧室场景中，需要确认床对象的使用状态和功能
