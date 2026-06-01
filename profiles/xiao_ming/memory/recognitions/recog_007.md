---
Description: 对象交互状态管理差异化机制
Time: 2026-06-01T12:56:36+00:00
Keywords: [状态绑定, 对象类型, 交互闭环]
Type: recognition
Importance: 9
Sources: [consolidated/consolidated_006.md, events/event_035.md, events/event_074.md]
---

通过多场景验证发现：常规对象需严格执行use→leave→finish闭环（床/浴缸），而冰箱等特例型对象自动触发use→finish模式。此认知基于事件_035/074冰箱自动状态释放与事件_037/059床对象强制leave_object的对比分析，揭示系统对象状态管理存在类型绑定差异
