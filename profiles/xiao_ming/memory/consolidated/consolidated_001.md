---
Description: 卧室→办公区→浴室跨区域交互流程
Time: 2026-05-30T16:19:12+00:00
Importance: 152
Keywords: [跨区域移动, 对象交互, 区域切换]
Type: consolidated
Sources: [events/event_005.md, events/event_010.md, events/event_014.md, events/event_022.md, events/event_025.md, events/event_026.md, events/event_028.md, events/event_031.md, events/event_032.md, events/event_034.md, events/event_070.md, events/event_018.md, events/event_057.md, events/event_066.md, events/event_082.md, recognitions/recog_006.md, recognitions/recog_001.md, events/event_043.md, events/event_053.md, recognitions/recog_008.md]
---

## 内容

跨区域交互管理强化：1. move_to_area需先行leave_object解除状态（事件018/033验证）。2. 新增卧室→浴室路径（事件053）、跨区移动前自动状态解锁（事件075）。3. 区域切换状态耦合机制：未解除状态将触发'Buff障碍'（事件018）
