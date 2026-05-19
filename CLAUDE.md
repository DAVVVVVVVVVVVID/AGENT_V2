# CLAUDE.md — AGENT_v1

## 项目背景

基于 ReAct 循环的基础 agent，运行在 BASIC_SANDBOX 沙盒中。
循环模块：Perceive → Think → Execute → 循环

## API 管理规则（必须遵守）

* 沙盒 API 标准化文件：`../SANDBOX/docs/api-spec.md`
* 每次对沙盒 API 进行任何增删改（新增接口、修改请求/响应结构、新增 action type），**必须同步更新** `../SANDBOX/docs/api-spec.md`
* agent 调用沙盒的所有接口均以此文件为准
