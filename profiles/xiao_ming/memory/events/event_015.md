---
Description: 用户结束办公区desk交互任务
Time: 2026-05-30T15:52:12+00:00
Keywords: [任务结束, leave_object, finish, 办公区, 交互终止]
Type: event
Importance: 6
---

## What
用户结束对办公区desk的交互任务，从using状态恢复至idle并完成任务

## How
调用leave_object工具退出desk对象交互，随后调用finish工具结束任务。关键步骤包括状态检查和连续工具调用，无需额外移动或转向操作

## Why
根据环境交互规则，使用后的对象需主动释放并结束任务流程

## Raw Actions
✓ leave_object() → {'objectId': 'desk_1779367828152'}
✓ finish(reply='成功结束办公区 desk 交互任务') → {'reply': '成功结束办公区 desk 交互任务'}
