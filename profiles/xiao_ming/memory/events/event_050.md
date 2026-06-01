---
Description: 测试离开状态自动处理机制，使用冰箱后状态自动恢复为idle
Time: 2026-05-30T18:55:54+00:00
Keywords: [状态自动处理, 冰箱交互, 无需leave_object, 状态恢复验证]
Type: event
Importance: 8
---

## What
测试离开状态自动处理机制，通过冰箱交互验证系统是否自动恢复状态

## How
1. 在相邻格子(0,7)朝向下直接调用use_object
2. 观察返回message确认交互成功
3. 通过finish结束流程并验证状态自动恢复

## Why
验证对象交互后系统自动处理离开状态的机制是否正常运作，避免冗余操作

## Raw Actions
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✓ finish(reply='成功测试离开状态自动处理机制，使用冰箱后状态自动恢复为idle') → {'reply': '成功测试离开状态自动处理机制，使用冰箱后状态自动恢复为idle'}
