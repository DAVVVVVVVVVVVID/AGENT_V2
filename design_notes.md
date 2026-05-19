# AGENT_v1 设计笔记

---

## 环境配置

### Python 环境
- 使用 **uv** 管理虚拟环境和依赖，与沙盒保持一致

### LLM 配置
- 模型：**qwen3:32b**（Q4_K_M 量化，20GB）
- 运行方式：本地 Ollama，Docker 容器 `ollama-gpu`，启动时需加 `--gpus all`
- API endpoint：`http://localhost:11435`（注意：非默认 11434）
- 使用 OpenAI 兼容接口：`http://localhost:11435/v1/chat/completions`
- **Tool Use**：支持，测试通过
- **思考模式**：Qwen3 默认开启，推理过程在 `reasoning` 字段，实际输出在 `content` / `tool_calls`

### 容器启动命令（备忘）
```bash
sudo docker run -d \
  --name ollama-gpu \
  --restart unless-stopped \
  --gpus all \
  -p 11435:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama:0.24.0
```

---

## 模块一：Perceive

### 已确认内容

**1. 所在 arena 完整树状信息（语义层）**
- 只提供语义信息：当前 arena 内有哪些 world / sector / arena / object，叫什么名字，是否可交互
- **不包含坐标等具体位置信息**
- LLM 根据需要自行判断，再调用对应 API 获取特定坐标信息

**2. 视野范围内 tile 信息（感知层）**
- 以 agent 为中心，视野边长（vision_size）默认为 3，即 3×3 范围
- 每个 tile 提供：坐标、所属 world / sector / arena、object（有则告知）
- 视野内属于其他 arena 的 tile：只提供 tile 信息，不展开其 arena 树状结构
- 定位：arena 树状信息是语义层（知道"这里有什么"），视野 tile 是感知层（知道"周围具体长什么样"），两者互补

**3. 自身状态变化（diff）**
- agent 维护上一次状态快照
- 每次 Perceive 时与当前状态做 diff，只输出发生变化的字段
- 监控的易变字段：`position`、`facing`、`state`、`stateLabel`、`hp`、`energy`、`buffs`、`tags`、`usingObjectId`

**4. 正前方格子信息**
- Perceive 额外输出正前方一格的内容
- Think 只关心：是否是 object，如果是，是什么 object

**5. 其他约定**
- 视野边长（vision_size）：agent 独立定义，默认值 3（3×3），偶数自动取奇；不依赖沙盒 player 字段
- 所有信息均通过沙盒标准 API 获取（见 `../SANDBOX/docs/api-spec.md`）
- 自身固定信息（姓名、性格、性别等）不在 Perceive 中出现，由 Think 模块打包提供

---

## 模块二：Think

### 输入信息

**1. Agent 个人参数**
- **性格特征**：使用 OCEAN 模型打分存储，根据分数动态生成描述性语言；生成逻辑单独封装为可复用的方法/文件
- **生活方式**：描述性句子列表，如 `["早上习惯于早起", "饭后喜欢喝牛奶"]`，直接描述输入
- 纯系统计算参数（如视野半径）不提供给 Think

**2. 当前任务目标**
- 由用户在 agent 启动时提供，全程携带直到 agent 完成任务

**3. 历史记忆（滚动窗口）**
- 存储内容：每轮的 Thought + Action + Observation
- 保留最近 10 轮，超出后自动丢弃最旧的记录

**4. 当前完整状态**
- 完整的当前玩家状态（非 diff，完整快照）
- Perceive 产出的环境感知：arena 语义树 + 视野 tile + 正前方 object 信息

### 输出：原子化行为（从以下选项中选一个）

**信息获取类**

| 行为 | 说明 |
|------|------|
| 获取某一 arena 的坐标范围 | 返回该 arena 包含的所有坐标 |
| 获取某一 object 的具体坐标 | 返回该 object 的位置 |

**沙盒交互类**

| 行为 | 说明 | API 状态 |
|------|------|----------|
| 位移到某一具体坐标 | 对应鼠标点击位移 | 已有 |
| 向某方向位移 N 格 | payload: `{"direction": "up", "steps": N}`，逐格执行，遇到不可行走格子停止 | 需修改 API |
| 转至某方向 | 不位移，只改变朝向 | 已有 |
| 使用物品 | 面向物品按 E | 已有 |
| 观察物品 | 面向物品按 I，获取描述 | 已有 |
| 离开物品 | 当前使用中，按 Q 离开 | 已有 |
| 位移到 world/sector/arena 随机位置 | 沙盒返回目标区域随机可行走坐标，内部用点击位移 API 执行移动 | 需新增 API |

### 待同步到 api-spec.md 的 API 变更

1. **修改**：`move` action 支持 `steps` 参数，`{"direction": "up", "steps": 3}`，逐格校验，遇阻停止
2. **新增**：移动到目标 world/sector/arena 随机可行走位置的 action type

---

## 模块三：Execute

### 输入
- Think 输出的结构化 tool call，格式如 `{"tool": "move_to", "args": {"x": 3, "y": 4}}`

### Tool Use 设计
- Think 调用 LLM 时，将所有可用行为定义为 tool（Function Calling / Tool Use 格式）
- LLM 直接输出结构化 tool call，无需额外的"描述性文字→API"翻译步骤
- Execute 接收 tool call，映射到对应的沙盒 HTTP 请求

### 参数变更
- 目前所有可变状态均属于沙盒 player，Execute 调用 API 后由沙盒负责更新
- 暂无 agent 独有的可变参数，此问题暂不处理

### 执行结果 → Observation
- 沙盒 API 返回结构化结果（`success`、`reason`、`result`）
- Execute 将结果转换为自然语言 Observation，存入历史记忆
- 每个 action type 对应固定模板生成 Observation，格式统一
- 示例：
  - 失败：`"尝试移动到 (1,1)，失败：目标格子不可行走"`
  - 成功：`"成功移动到 (3,4)，当前朝向：上"`

---

## 模块四：循环机制

### 循环触发
- Execute 完成后（无论成功或失败），Observation 生成完毕即触发下一次 Perceive → Think → Execute 循环
- 超时机制（Execute 长时间未结束时强制进入下一循环）暂不实现，后续再添加

### 循环结束
- Think 的可选行为中加入特殊的 `finish` action
- LLM 在 Think 阶段判断任务已完成时选择 `finish`，并在 action 参数中直接生成对原始任务目标的总结回复
- 循环主控检测到 `finish` 时停止循环，输出该总结回复
- 结束后不再单独跑 LLM，总结由 `finish` action 内直接产出

### finish action 补充到 Think 模块行为列表

| 行为 | 说明 | API 状态 |
|------|------|----------|
| finish | 判断任务完成，附带总结回复文字，终止循环 | 无需调用沙盒 API |
