---
Description: 跨区域移动的解除交互前提
Time: 2026-06-01T12:56:36+00:00
Keywords: [区域切换, 状态解除, 交互前提]
Type: recognition
Importance: 8
Sources: [recognitions/recog_001.md, events/event_075.md]
---

卧室→办公区等跨区域转移需先通过leave_object解除状态。事件_018显示未解除状态会导致'Buff障碍'，而事件_075验证cross_area后系统会自动解除冰箱交互状态，揭示区域切换与状态管理的强耦合关系
