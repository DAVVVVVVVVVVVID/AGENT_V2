---
Description: 小明成功从卧室移动到工作区域并定位书桌对象
Time: 2026-05-30T12:13:52+00:00
Keywords: [区域移动, 书桌定位, 任务完成]
Type: event
Importance: 8
---

## What
小明在卧室区域(2,3)左方向出发，通过move_to_area跨区域移动至工作区域(6,3)右方向，完成书桌对象定位

## How
{'使用行动': ['move_to_area', 'finish'], '关键步骤': ['调用move_to_area(arena,workplace)实现跨区域传送', '在目标区域验证坐标(6,3)和方向(right)', '调用finish确认任务完成'], '障碍': '无明显障碍，行动全程成功'}

## Why
执行用户下达的『前往工作区域定位书桌对象』任务指令，符合工作场景交互需求
