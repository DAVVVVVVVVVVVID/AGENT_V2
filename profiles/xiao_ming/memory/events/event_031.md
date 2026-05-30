---
Description: 小明通过调用move_to_area从卧室成功移动至工作区域
Time: 2026-05-30T12:20:06+00:00
Keywords: [移动验证, 工作区, move_to_area, 坐标变换, 任务完成]
Type: event
Importance: 6
---

## What
验证从卧室到工作区域的移动功能，实际完成跨区域移动并触发finish

## How
1. 分析当前位置和目标区域参数；2. 调用move_to_area('arena','workplace')；3. 确认坐标从(1,8)左转向(6,8)右；4. 调用finish()结束任务。无异常障碍

## Why
验证跨区域移动功能在卧室到工作场景的正确执行
