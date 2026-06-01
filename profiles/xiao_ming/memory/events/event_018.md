---
Description: 小明成功通过move_to_area完成跨区域移动从浴室到卧室
Time: 2026-05-30T15:55:24+00:00
Keywords: [跨区域移动, 卧室, move_to_area, 任务完成, 区域切换]
Type: event
Importance: 7
---

## What
执行跨区域移动任务从浴室区域到卧室区域

## How
{'key_steps': ["调用move_to_area(area_type='arena', area_id='bedroom')切换区域", '确认目标区域坐标位置(x=2,y=3)和朝向(down)', '执行finish()确认任务完成'], 'obstacles': '无记录中的障碍'}

## Why
完成用户指定的跨区域移动任务，为后续卧室区域操作建立位置基础

## Raw Actions
✓ move_to_area(area_type='arena', area_id='bedroom') → {'position': {'x': 2, 'y': 3}, 'facing': 'down'}
✓ finish(reply='成功跨区域移动至卧室区域') → {'reply': '成功跨区域移动至卧室区域'}
