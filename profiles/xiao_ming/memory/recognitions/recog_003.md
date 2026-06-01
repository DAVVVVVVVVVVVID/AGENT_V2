---
Description: 对象交互闭环的两种模式
Time: 2026-05-30T16:19:33+00:00
Keywords: [交互模式, 状态管理, 对象特性]
Type: recognition
Importance: 7
Sources: [consolidated/consolidated_002.md, consolidated/consolidated_003.md, consolidated/consolidated_004.md, consolidated/consolidated_005.md]
---

发现两种标准收尾模式：1) 常规型：use_object → leave_object → finish(如床/浴缸/办公桌)；2) 特例型：直接finish无需leave_object(如冰箱)。这种分野源于对象状态绑定机制差异，需要针对性策略
