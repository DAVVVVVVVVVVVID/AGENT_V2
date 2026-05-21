# CLAUDE.md — AGENT_v2

## 项目背景

在 AGENT_v1（ReAct 循环）基础上演进的自驱动 agent，运行在 BASIC_SANDBOX 沙盒中。

核心改进：
- **自驱动循环**：Purpose → Plan → Action，不再依赖手动任务输入
- **记忆系统**：Event 记忆 + Recognition 记忆 + Purpose 文件
- **Retrieve 阶段**：Perceive 之后、Think 之前，独立小型 LLM 执行两步 KW 检索
- **Action Sequence**：Think 每次输出多个原子行动，而非单个

循环模块：Perceive → Retrieve → Think（输出行动序列）→ Execute（逐步）→ 循环

## 设计文档

详细设计见 `design_notes.md`，涵盖：
- 记忆文件结构与格式
- 两步检索机制与 Importance 公式
- Purpose → Plan → Action 三层循环
- 影子 Agent（Shadow Agent）
- 与 AGENT_v1 的差异对比

## API 管理规则（必须遵守）

* 沙盒 API 标准化文件：`../SANDBOX/docs/api-spec.md`
* 每次对沙盒 API 进行任何增删改（新增接口、修改请求/响应结构、新增 action type），**必须同步更新** `../SANDBOX/docs/api-spec.md`
* agent 调用沙盒的所有接口均以此文件为准
