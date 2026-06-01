---
Description: 对象交互状态管理存在绑定类型差异
Time: 2026-06-01T10:25:59+00:00
Keywords: [状态绑定, 交互闭环, 对象分类]
Type: recognition
Importance: 9
Sources: [events/event_035.md, events/event_037.md, consolidated/consolidated_006.md]
---

通过冰箱/床/浴缸等对象交互案例发现：常规对象需遵循use→leave闭环（如床交互事件_037、059、023），而冰箱交互后状态自动释放无需主动离开（事件_048、051、073）。此差异导致跨区域移动前需判断对象类型：普通对象必须显式解除绑定，冰箱可直接移动，这解释了为何浴室到卧室move_to_area成功事件_018无状态阻碍，而办公区desk需强制leave。
