# 持仓导入到虚拟账户 — 设计文档

**日期：** 2026-03-22
**版本：** v1.1
**目标：** 在持仓诊断页支持将当前持仓一键推送到虚拟账户，打通"持仓分析 → 模拟投资"用户流程闭环。

---

## 一、背景与目标

当前持仓诊断页（`2_portfolio.py`）和策略验证页（`3_strategy_lab.py`）是独立的，用户无法将诊断后的持仓直接送入虚拟账户。本功能在持仓诊断页新增"发送到虚拟账户"入口，实现显式推送。

**不做的事：**
- 跨页面双向同步状态
- 精确 NAV 计算（统一使用 NAV=1.0）
- 批量操作失败的部分回滚（见 4.8）

---

## 二、架构分层

```
ui/pages/2_portfolio.py
    ↓ 调用
service/simulation_service.py  ← 新增 import_holdings()
    ↓ 调用（已有）
domain/simulation/account.py   ← 零改动
    ↓
infrastructure/storage/sqlite_store.py  ← 零改动
```

依赖方向严格单向：`ui → service → domain → infrastructure`，domain 层零 IO。

**说明：** `SimulationService` 现有方法（`_update_account`, `_persist_account`）已直接使用 SQL 操作数据库，`import_holdings()` 遵循同一模式，不违反现有架构边界。

---

## 三、文件变更清单

| 文件 | 动作 |
|---|---|
| `service/simulation_service.py` | 新增 `import_holdings()` 方法 |
| `ui/pages/2_portfolio.py` | 新增「发送到虚拟账户」UI 区块 |
| `tests/service/test_simulation_service.py` | 新增 `import_holdings` 相关测试 |

**不变动：**
- `domain/` 任何文件
- `infrastructure/` 任何文件
- `ui/pages/3_strategy_lab.py`（无需修改，页面跳转由 `st.page_link` 实现）

---

## 四、SimulationService.import_holdings() 规格

### 4.1 函数签名

```python
def import_holdings(
    self,
    holdings: list[dict],        # 标准结构：[{"fund_code","fund_name","amount"}]
    account_id: str,             # 必填，由 UI 侧用户填写
    mode: str = "append",        # "append" | "replace"，其他值抛 ValueError
    initial_cash: float = 0.0,   # 仅新建账户时使用，必须 >= holdings 总金额
    nav: float = 1.0,            # 本轮固定为 1.0，接口预留可覆盖
) -> dict:
```

**设计决策：** `account_id` 为必填参数，不支持自动生成。UI 侧需用户提供账户 ID（新建或选择已有）。

### 4.2 返回结构

```python
{
    "account": VirtualAccount,
    "created_new_account": bool,
    "imported_count": int,
    "skipped_count": int,   # 预留字段，本轮始终为 0
    "mode": str,
    "nav_used": float,
    "message": str,
}
```

### 4.3 新建账户判断

通过 `get_account(account_id)` 判断账户是否存在：
- 返回 `None` → 新建账户，调用 `create_account(account_id, initial_cash)`
- 返回账户对象 → 已有账户，继续执行

新建账户时 `initial_cash` 必须 ≥ holdings 总金额，否则 `ValueError`。

### 4.4 replace 模式（重建账户状态）

replace 模式在内存中操作 `VirtualAccount` 对象，最后一次性持久化，避免中间读取 DB 导致状态不一致。

**执行步骤：**

1. **获取或创建账户对象**
   - 新建：调用 `create_account()` 并获取返回的 `VirtualAccount`
   - 已有：调用 `get_account()` 获取 `VirtualAccount`

2. **清空内存中账户对象的状态**
   - `account.positions = []`
   - `account.trades = []`
   - `account.cash = account.initial_cash`

3. **执行买入操作**（在内存中）
   - 对每条 holding 调用 `buy(account, fund_code, fund_name, amount, nav=1.0, reason="...")`
   - `buy()` 会更新 `account.cash`、`account.positions`、生成 `Trade` 对象

4. **一次性持久化到数据库**
   - 使用事务执行以下 SQL：
   ```sql
   -- 清空旧数据
   DELETE FROM virtual_account_equity_curve WHERE account_id = ?;
   DELETE FROM virtual_account_position WHERE account_id = ?;
   DELETE FROM trade_record WHERE account_id = ?;
   -- 重置账户现金
   UPDATE virtual_account SET cash = ? WHERE account_id = ?;
   -- 插入新持仓
   INSERT INTO virtual_account_position (...) VALUES (...);
   -- 插入新交易记录
   INSERT INTO trade_record (...) VALUES (...);
   ```

**语义：** replace = 重建虚拟账户当前状态，不保留旧持仓、旧交易记录、旧权益曲线。

**trade_id 规则与限制：**
- 现有 `buy()` 函数生成的 trade_id 格式：`{account_id}_{fund_code}_{YYYYMMDD}_{action}`
- **replace 模式：** 先清空 trade_record 表，再插入新记录，无主键冲突风险
- **append 模式：** 若同日多次追加同一 fund_code，trade_id 会冲突导致 `IntegrityError`
- 这是现有系统的限制（`execute_buy` 同样存在），本轮不解决，追加到文档"已知限制"章节

### 4.5 append 模式

append 模式直接复用现有 `execute_buy()` 方法，逐条执行买入：

1. 账户当前 `cash` 必须 ≥ holdings 总金额，否则 `ValueError`
2. 对每条 holding 调用 `execute_buy()`，已有同 `fund_code` 持仓会自动累加（domain 层 buy 逻辑已支持）

### 4.6 mode 参数验证

方法入口处验证 `mode` 参数：
```python
if mode not in ("append", "replace"):
    raise ValueError(f"Invalid mode: {mode}. Must be 'append' or 'replace'.")
```

### 4.7 NAV 与持仓字段规则

| 字段 | 值 |
|---|---|
| `nav` | 1.0（固定） |
| `shares` | = amount（由 domain buy 计算） |
| `cost_nav` | 1.0 |
| `reason` | `"从持仓诊断页导入，按 NAV=1.0 初始化模拟持仓"` |

### 4.8 输入要求

`import_holdings()` 只接受已标准化的持仓列表：

```python
[{"fund_code": "000001", "fund_name": "示例基金A", "amount": 10000.0}, ...]
```

CSV 解析由前端导入模块负责，service 不处理原始 CSV。

### 4.9 holdings 为空的行为

| 模式 | 行为 |
|---|---|
| append | `imported_count=0`，账户状态不变，正常返回 |
| replace | 清空账户持仓和交易记录，cash 重置为 initial_cash，`imported_count=0` |

### 4.10 部分失败行为

**不做事务回滚：** 若买入过程中某条 holding 失败（如 fund_code 无效），直接抛出 `ValueError`，已执行的修改不回滚。

这是明确的设计取舍，与"不做的事"中的"批量操作失败的部分回滚"一致。

---

## 五、UI 设计（2_portfolio.py）

在当前持仓区块下方、"清空持仓"按钮之后，新增折叠区块。

**显示条件：** 仅当 `st.session_state.holdings` 非空时渲染整个 expander。无持仓时不显示该区块。

### 5.1 布局结构

```
📤 发送到虚拟账户          [st.expander, 默认折叠，仅持仓非空时显示]
  st.info("⚠️ 所有持仓将按 NAV=1.0 建仓，仅用于建立模拟起点，不代表真实持仓成本。")

  目标账户类型 [st.radio]
    ○ 新建账户   ● 已有账户

  [新建账户时显示]
    账户 ID     [st.text_input, placeholder="输入新账户 ID"]
    初始资金    [st.number_input, min=持仓总金额, value=持仓总金额]

  [已有账户时显示]
    账户 ID     [st.text_input, placeholder="输入已有账户 ID"]

  导入模式 [st.radio]
    ● 追加到现有持仓   ○ 替换现有持仓

  [确认导入]  st.button(type="primary")
```

### 5.2 成功状态

```
st.success("✅ 已将 N 条持仓导入账户 XXX（模式：追加/替换）")
st.page_link("pages/3_strategy_lab.py", label="前往策略验证页查看 →")
```

**路径验证：** `pages/3_strategy_lab.py` 是相对于 `ui/` 目录的 Streamlit 多页面标准路径，与现有页面结构一致。

### 5.3 错误状态

| 情况 | 提示 |
|---|---|
| 账户 ID 为空 | `st.warning("请输入账户 ID")` |
| 新建账户初始资金不足 | `st.error("初始资金必须 ≥ 持仓总金额 ¥X")` |
| 已有账户余额不足（append） | `st.error("账户余额不足，无法追加导入。当前余额：¥X，需要：¥Y")` |
| 账户不存在（已有账户） | `st.error("未找到账户 XXX，请先在策略验证页创建账户")` |
| mode 参数无效 | `st.error("无效的导入模式")`（代码层面已验证，UI 不应触发） |

### 5.4 导入模式可见性

"导入模式"选项仅在选择"已有账户"时显示。新建账户时强制使用 replace 语义，无需用户选择模式。

---

## 六、测试覆盖

新增测试写入 `tests/service/test_simulation_service.py`：

| 测试用例 | 验证点 |
|---|---|
| 新建账户 + replace | 账户创建成功、持仓数量正确、cash 正确 |
| 已有账户 + append | 同 fund_code 持仓合并、交易记录追加 |
| 已有账户 + replace | 旧持仓清空、旧交易记录清空、旧权益曲线清空、持仓重建 |
| initial_cash 不足（新建） | `ValueError` |
| cash 不足（append） | `ValueError` |
| holdings 为空 + append | `imported_count=0`，账户状态不变 |
| holdings 为空 + replace | 持仓和交易记录清空，cash 重置，`imported_count=0` |
| account_id 不存在（append） | `ValueError` |
| mode 参数无效 | `ValueError("Invalid mode: ...")` |
| 返回结构字段完整性 | 所有 key 都存在 |
| 同日多次 replace | trade_id 不冲突，每次导入独立成功 |
| 同 fund_code 多次 append | 持仓金额累加、shares 累加、多条交易记录 |

---

## 七、不在本轮范围内

- 精确 NAV：读取 akshare 实时净值作为买入价格
- 部分持仓跳过：本轮 `skipped_count` 始终为 0
- 从虚拟账户反向导出到持仓页
- 多账户批量操作

---

## 八、已知限制

| 限制 | 说明 | 影响 |
|---|---|---|
| 同日同基金追加 trade_id 冲突 | 现有 `_generate_trade_id` 不包含随机因子，同日追加同一 fund_code 会主键冲突 | append 模式下，同一天不能多次导入相同基金 |
| 无部分回滚 | 任一 holding 失败即抛异常，已执行操作不回滚 | 用户需手动清理或重试 |

**未来改进方向：**
- trade_id 改用 UUID 或添加序号后缀
- 支持事务回滚或记录失败项继续执行
