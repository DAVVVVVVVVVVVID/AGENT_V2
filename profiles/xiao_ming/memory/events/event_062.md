---
Description: 浴缸交互方向校准验证流程通过系统自检
Time: 2026-05-30T19:11:36+00:00
Keywords: [交互校准, 方向验证, 浴室设备]
Type: event
Importance: 8
---

## What
验证浴室小明浴缸的交互方向校准有效性，完成标准交互流程测试

## How
通过use_object确认校准有效性→leave_object结束交互→finish上报验证结果，全程无异常

## Why
确保交互系统方向校准符合设计规范，规避错误操作风险

## Raw Actions
✓ use_object() → {'objectId': 'bath_1779367293480', 'stateLabel': '小明 正在使用', 'message': '躺进浴缸，整个人都舒畅了'}
✓ leave_object() → {'objectId': 'bath_1779367293480'}
✓ finish(reply='完成bath交互方向校准验证，交互流程符合标准操作要求。') → {'reply': '完成bath交互方向校准验证，交互流程符合标准操作要求。'}
