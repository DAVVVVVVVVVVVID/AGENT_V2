---
Description: 浴缸交互修正流程
Time: 2026-05-30T16:19:12+00:00
Importance: 57
Keywords: [路径修正, 方向绑定, 失败重试]
Type: consolidated
Sources: [events/event_008.md, events/event_013.md, events/event_016.md, events/event_017.md, events/event_022.md, events/event_026.md, events/event_027.md, events/event_032.md]
---

## 内容

关键控制点：
1. (1,0)标准交互位点定位
2. left/facing left严格方向要求
3. 失败重试机制（move_to_area重试）
4. use_object-leave_object闭包
典型障碍：首次错误move_to(2,4)需位置修正
