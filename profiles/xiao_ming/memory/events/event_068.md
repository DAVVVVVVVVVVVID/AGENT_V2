---
Description: 调整朝向为右方向以成功交互办公区desk对象
Time: 2026-05-30T19:23:59+00:00
Keywords: [方向调整, 成功交互, 办公区desk, turn行动, 方位验证]
Type: event
Importance: 7
---

## What
用户通过调整朝向从下转向右，使正前方对准(10,0)位置的desk对象

## How
{'description': "1. 执行turn({'direction': 'right'})调整方向 2. 验证当前方向后调用finish()确认完成", 'type': 'string'}

## Why
根据历史记录，办公区desk对象的交互需满足右向朝前提条件下

## Raw Actions
✓ turn(direction='right') → {'facing': 'right'}
✓ finish(reply='已调整朝向为右，正对办公区desk对象') → {'reply': '已调整朝向为右，正对办公区desk对象'}
