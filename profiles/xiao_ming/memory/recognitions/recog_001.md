---
Description: 跨区域移动需前置解除交互状态
Time: 2026-05-30T16:19:33+00:00
Keywords: [状态管理, 区域切换, 交互前提]
Type: recognition
Importance: 9
Sources: [events/event_018.md, events/event_033.md, consolidated/consolidated_001.md, consolidated/consolidated_004.md]
---

通过卧室到办公区案例(event_018)和浴缸解除状态(event_033)发现：执行move_to_area前必须通过leave_object解除当前交互状态。否则会产生'无法移动/互动的Buff状态'等障碍，这已被多次成功验证(consolidated_001/004)
