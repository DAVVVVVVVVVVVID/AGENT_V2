---
Description: 用户成功离开床并探索了卧室中的冰箱对象
Time: 2026-05-30T11:34:57+00:00
Keywords: [卧室探索, 物体交互, 空间导航, 状态转换, 目标达成]
Type: event
Importance: 7
---

## What
用户从床的使用状态中离开，定位冰箱并完成物体交互，最终成功使用冰箱

## How
用户分阶段执行：1.调用leave_object解除床的锁定 2.使用get_object_position获取冰箱坐标(0,8) 3.通过move_to_tile移动到(1,8) 4.向left方向调整朝向 5.执行use_object完成交互

## Why
为完成卧室环境探索目标，需突破当前物理状态限制（使用床的锁定状态）并建立空间定位导航能力
