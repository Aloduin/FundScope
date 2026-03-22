# 持仓导入到虚拟账户 — 设计文档

**日期：** 2026-03-22
**版本：** v1.0
**目标：** 在持仓诊断页支持将当前持仓一键推送到虚拟账户，打通"持仓分析 → 模拟投资"用户流程闭环。

---

## 一、背景与目标

当前持仓诊断页（`2_portfolio.py`）和策略验证页（`3_strategy_lab.py`）是独立的，用户无法将诊断后的持仓直接送入虚拟账户。本功能在持仓诊断页新增"发送到虚拟账户"入口，实现显式推送。

**不做的事：**
- 跨页面双向同步状态
- 精确 NAV 计算（统一使用 NAV=1.0）
- 批量操作失败的部分回滚

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
    mode: str = "append",        # "append" | "replace"
    account_id: str | None = None,  # None → 新建账户
    initial_cash: float = 0.0,   # 新建账户时必须 >= holdings 总金额
    nav: float = 1.0,            # 本轮固定为 1.0，接口预留可覆盖
) -> dict:
```

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

### 4.3 新建账户路径（account_id is None）

1. 自动生成或要求调用方传入 `account_id`（UI 侧由用户填写）
2. `initial_cash` 必须 ≥ holdings 总金额，否则 `ValueError`
3. 调用现有 `create_account(account_id, initial_cash)` 创建账户
4. 之后执行 **replace 逻辑**

### 4.4 replace 模式

按顺序执行：

1. 直接通过 SQL 清空持仓：`DELETE FROM virtual_account_position WHERE account_id = ?`
2. 直接通过 SQL 清空交易记录：`DELETE FROM trade_record WHERE account_id = ?`
3. 重置账户现金：
   - 新建账户：cash = initial_cash（由 `create_account` 已设定）
   - 已有账户：cash 重置为账户的 `initial_cash`
4. 对每条 holding 执行 `execute_buy(account_id, fund_code, fund_name, amount, nav=1.0, reason="从持仓诊断页导入，按 NAV=1.0 初始化模拟持仓")`

**语义：** replace = 重建虚拟账户当前状态，不保留旧持仓与旧交易记录。

### 4.5 append 模式

1. 账户当前 `cash` 必须 ≥ holdings 总金额，否则 `ValueError`
2. 对每条 holding 执行 `execute_buy()`，已有同 `fund_code` 持仓会自动累加（domain 层 buy 逻辑已支持）

### 4.6 NAV 与持仓字段规则

| 字段 | 值 |
|---|---|
| `nav` | 1.0（固定） |
| `shares` | = amount（由 domain buy 计算） |
| `cost_nav` | 1.0 |
| `reason` | `"从持仓诊断页导入，按 NAV=1.0 初始化模拟持仓"` |

### 4.7 输入要求

`import_holdings()` 只接受已标准化的持仓列表：

```python
[{"fund_code": "000001", "fund_name": "示例基金A", "amount": 10000.0}, ...]
```

CSV 解析由前端导入模块负责，service 不处理原始 CSV。

---

## 五、UI 设计（2_portfolio.py）

在当前持仓区块下方、"清空持仓"按钮之后，新增折叠区块。

### 5.1 布局结构

```
📤 发送到虚拟账户          [st.expander, 默认折叠]
  st.info("⚠️ 所有持仓将按 NAV=1.0 建仓，仅用于建立模拟起点，不代表真实持仓成本。")

  目标账户类型 [st.radio]
    ○ 新建账户   ● 已有账户

  [新建账户时显示]
    账户 ID     [st.text_input]
    初始资金    [st.number_input, min=持仓总金额]

  [已有账户时显示]
    账户 ID     [st.text_input]

  导入模式 [st.radio]
    ● 追加到现有持仓   ○ 替换现有持仓

  [确认导入]  st.button(type="primary")
```

### 5.2 成功状态

```
st.success("✅ 已将 N 条持仓导入账户 XXX（模式：追加/替换）")
st.page_link("pages/3_strategy_lab.py", label="前往策略验证页查看 →")
```

### 5.3 错误状态

| 情况 | 提示 |
|---|---|
| 账户 ID 为空 | `st.warning("请输入账户 ID")` |
| 新建账户初始资金不足 | `st.error("初始资金必须 ≥ 持仓总金额 ¥X")` |
| 已有账户余额不足（append） | `st.error("账户余额不足，无法追加导入。当前余额：¥X，需要：¥Y")` |
| 账户不存在（已有账户） | `st.error("未找到账户 XXX，请先在策略验证页创建账户")` |
| holdings 为空 | `st.warning("当前无持仓，请先添加持仓")` |（按钮不渲染）|

---

## 六、测试覆盖

新增测试写入 `tests/service/test_simulation_service.py`：

| 测试用例 | 验证点 |
|---|---|
| 新建账户 + replace | 账户创建成功、持仓数量正确、cash 正确 |
| 已有账户 + append | 同 fund_code 持仓合并、交易记录追加 |
| 已有账户 + replace | 旧持仓清空、旧交易记录清空、持仓重建 |
| initial_cash 不足（新建） | `ValueError` |
| cash 不足（append） | `ValueError` |
| holdings 为空 | `imported_count=0`，不报错，账户不变 |
| account_id 不存在（已有账户） | `ValueError` |
| 返回结构字段完整性 | 所有 key 都存在 |

---

## 七、不在本轮范围内

- 精确 NAV：读取 akshare 实时净值作为买入价格
- 部分持仓跳过：本轮 `skipped_count` 始终为 0
- 从虚拟账户反向导出到持仓页
- 多账户批量操作
