---
Description: 成功通过use_object与冰箱交互并结束任务，但leave_object调用失败
Time: 2026-05-30T16:00:05+00:00
Keywords: [冰箱交互, use_object, leave_object失败, 任务结束, 状态异常]
Type: event
Importance: 6
---

## What
用户多次尝试通过use_object使用冰箱后调用finish结束任务，但leave_object始终失败

## How
使用use_object触发冰箱交互并获得反馈，因leave_object失败直接调用finish结束任务。共尝试5次交互，其中前4次leave_object失败，最后一次直接调用finish成功

## Why
系统交互机制要求先调用leave_object退出使用状态后再finish，但用户可能未正确进入using状态导致调用链异常

## Raw Actions
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✗ leave_object() → 当前没有正在使用的对象
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✗ leave_object() → 当前没有正在使用的对象
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✗ leave_object() → 当前没有正在使用的对象
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✓ use_object() → {'objectId': 'fridge_1779367415680', 'stateLabel': None, 'message': '好吃！'}
✓ finish(reply='成功完成冰箱交互并结束任务') → {'reply': '成功完成冰箱交互并结束任务'}
