---
Description: 小明通过move_to_area指令完成卧室到工作区域的跨场所移动
Time: 2026-05-30T11:42:38+00:00
Keywords: [场所迁徙, move_to_area, 工作区导航, 卧室到办公区, 跨区域移动]
Type: event
Importance: 7
---

## What
小明从卧室(4,3)移动至工作区域(6,3)，完成场所转换

## How
1. 调用move_to_area({"area_type": "arena", "area_id": "workplace"})实现跨区域导航
2. 验证坐标(6,3)确认位于工作区域
3. 使用finish()确认任务完成

## Why
执行用户指令要求的场所迁移操作
