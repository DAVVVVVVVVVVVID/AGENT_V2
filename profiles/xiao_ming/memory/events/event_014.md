---
Description: 成功从卧室区域移动至工作区域
Time: 2026-05-30T11:47:53+00:00
Keywords: [区域移动, 成功完成, 工作场所, 导航, 状态确认]
Type: event
Importance: 5
---

## What
执行从卧室(bedroom)到工作区域(workplace)的区域转移

## How
1. 使用move_to_area函数指定area_type为arena，area_id为workplace
2. 系统反馈移动成功并处于(6,7)坐标位置
3. 第二轮通过finish()确认目标达成

## Why
根据环境结构数据确认工作区域存在且可用移动函数直达
