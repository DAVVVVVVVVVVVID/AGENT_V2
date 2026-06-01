---
Description: 卧室冰箱交互流程
Time: 2026-06-01T12:56:07+00:00
Importance: 32
Keywords: [冰箱交互, 流程优化, 状态自动处理]
Type: consolidated
Sources: [events/event_035.md, events/event_048.md, events/event_051.md, events/event_071.md, events/event_079.md]
---

## 内容

冰箱标准化交互流程：1.核心流程：get_object_position→move_to_tile(0,7)→turn down→use_object→finish。2.关键特性：无需leave_object，成功率达100%（事件_035/048/051/074/082）。3.验证案例：包含3步移动+1步交互的标准模式（事件_051）与优化流程（事件_074）。4.异常处理：手动leave_object失败后系统自动恢复验证（事件_071/079）
