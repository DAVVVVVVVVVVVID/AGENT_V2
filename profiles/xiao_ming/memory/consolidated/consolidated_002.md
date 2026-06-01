---
Description: 床对象交互标准流程
Time: 2026-05-30T16:19:12+00:00
Importance: 142
Keywords: [床交互, 位置验证, 方向校准]
Type: consolidated
Sources: [events/event_001.md, events/event_003.md, events/event_004.md, events/event_012.md, events/event_023.md, events/event_029.md, events/event_030.md, events/event_039.md, events/event_040.md, events/event_067.md, events/event_072.md, events/event_063.md, events/event_081.md, recognitions/recog_005.md, events/event_047.md, events/event_043.md, events/event_052.md, events/event_076.md, events/event_086.md, recognitions/recog_009.md]
---

## 内容

床交互四向量模型：坐标(0,3)→(2,3)/0,6)移动→左向校准→use/leave闭环。失败案例：右向错误(事件039)。新增位置验证机制(事件085)。方向绑定误差率降低至15%以下(事件068方向修正验证)
