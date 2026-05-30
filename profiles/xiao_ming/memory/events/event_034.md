---
Description: 小明完成卧室床和冰箱的交互完整性检查
Time: 2026-05-30T12:25:52+00:00
Keywords: [卧室场景, 交互验证, 对象定位, 路径导航, 功能检查]
Type: event
Importance: 8
---

## What
小明依次与卧室中的床和冰箱进行完整交互，包括定位对象、移动到可操作位置、使用对象并结束交互

## How
1.调用get_object_position定位床和冰箱
2.通过move_to_tile移动到相邻格子
3.调整方向使用use_object
4.床交互后调用leave_object
5.冰箱交互后直接调用finish
障碍：初始方向调整错误导致冰箱使用失败，需修正坐标移动

## Why
确保卧室场景中所有功能对象能正常交互，验证导航和交互流程的完善性
