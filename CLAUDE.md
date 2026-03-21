# FundScope — 项目开发规范

---

## 一、环境管理

- 本项目使用 **uv** 管理 Python 环境和依赖
- 添加依赖：`uv add <package>`
- 运行脚本：`uv run <script>`
- 同步依赖：`uv sync`

### Python 版本
- 优先使用 **Python 3.13**
- 若第三方库兼容性不足，回退至 **Python 3.12**

---

## 二、版本管理

- 远程仓库：https://github.com/Aloduin/FundScope.git

### 提交规范
- 每次功能开发完成后，必须 commit 并 push
- commit 信息需清晰描述改动内容
  - 推荐格式：
    - `feat:` 新功能
    - `fix:` 修复问题
    - `refactor:` 重构
    - `docs:` 文档
    - `chore:` 其他

### 分支策略
- MVP 阶段允许主干开发
- 后续建议按功能建立 `feature/*` 分支

---

## 三、架构约束（不可违反）

1. 依赖方向严格单向：
   `ui → service → domain → infrastructure`

2. `domain` 层零 IO：
   - 不调用 akshare
   - 不读写文件 / 数据库
   - 仅处理 dataclass / DataFrame

3. 数据源可插拔：
   所有数据获取必须通过 `AbstractDataSource`

4. 存储访问收口：
   SQLite / Parquet 读写仅允许在
   `infrastructure/storage/` 内实现

5. 回测成交规则：
   - T 日产生信号
   - T+1 净值成交
   - 必须在代码注释中标注：`# 简化回测假设`

6. 信号结构统一：
   所有策略必须返回标准化 `Signal` dataclass

---

## 四、代码设计原则

### 1. 单一职责原则
每个模块只负责一件事：
- fund → 指标 / 评分 / 对比
- portfolio → 组合分析
- backtest → 回测逻辑
- simulation → 模拟账户

---

### 2. 禁止跨层调用
❌ 错误：
- ui 直接调用 infrastructure
- domain 调用 sqlite / akshare

✅ 正确：
- ui → service → domain → infrastructure

---

### 3. 配置与逻辑分离
- 所有可调参数必须写入 `shared/config.py`
- 不允许硬编码（如评分权重、阈值）

---

### 4. 数据结构优先
优先使用：
- dataclass
- 明确类型定义

避免：
- dict 到处传递（降低可维护性）

---

## 五、回测与策略规范

### 回测原则
- 禁止未来函数（仅使用当前及历史数据）
- 所有策略必须通过 `Strategy` 接口实现

### 策略分类（MVP）
- 定投（DCA）
- 均线择时
- 动量轮动

### 信号规则
- BUY / SELL / REBALANCE / HOLD
- 支持：
  - 金额型（amount）
  - 权重型（target_weight）

---

## 六、数据规范

### Parquet（时序数据）
- 按基金代码分文件
- 标准字段：
  - date
  - nav
  - acc_nav
  - return

---

### SQLite（业务数据）
- 所有表必须有主键
- 必须建立索引（fund_code / date 等）

---

## 七、缓存策略

- L1：内存缓存（短期）
- L2：文件缓存（跨天）

避免重复请求数据源（akshare）

---

## 八、测试规范

- 优先测试 `domain` 层
- 每个子域独立测试：
  - fund
  - portfolio
  - backtest
  - simulation

---

## 九、日志与调试

- 使用统一 logger（shared/logger.py）
- 不允许随意 print
- 关键步骤必须记录日志：
  - 数据加载
  - 回测执行
  - 策略信号

---

## 十、非目标（Out of Scope）

MVP 阶段不包含：

- ❌ 实盘交易对接
- ❌ 自动下单
- ❌ 多用户系统
- ❌ 云端部署
- ❌ 高频交易策略

---

## 十一、MVP 最小闭环

第一阶段必须实现：

1. 基金数据获取
2. 指标计算 + 基金评分
3. 赛道筛选与横向对比
4. 持仓分析与组合诊断
5. 回测引擎运行（至少1种策略）
6. Streamlit 三页面可用

---

## 十二、设计目标

本项目目标不是做"推荐买什么基金"，而是构建：

> **数据驱动 + 策略可验证 + 决策可解释 的基金投资系统**
