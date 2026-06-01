---
Description: 对象状态管理规则
Time: 2026-05-30T18:43:41+00:00
Importance: 76
Keywords: [状态闭环, 交互前提, 状态绑定]
Type: consolidated
Sources: [events/event_033.md, recognitions/recog_003.md, events/event_035.md, events/event_037.md, recognitions/recog_004.md, events/event_048.md, events/event_074.md, recognitions/recog_007.md, events/event_050.md, events/event_078.md, recognitions/recog_012.md]
---

## 内容

对象状态机模式强化：1)闭包型（床/浴缸：use→leave→finish） 2)非绑定型（冰箱：use→finish） 3)跨区域型（自动解捆）。模式差异导致17%异常（事件098）。新增验证显示闭包型需强制leave_object（事件078），非绑定型自动释放（事件050）。补充跨区自动解捆规则（move_to_area触发）
