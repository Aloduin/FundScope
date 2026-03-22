# 持仓导入到虚拟账户 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在持仓诊断页支持将当前持仓一键推送到虚拟账户，打通"持仓分析 → 模拟投资"用户流程闭环。

**Architecture:** 新增 `SimulationService.import_holdings()` 方法处理导入逻辑，UI 层在 `2_portfolio.py` 新增折叠区块收集用户输入。replace 模式在内存中操作后一次性持久化，append 模式复用现有 `execute_buy()`。

**Tech Stack:** Python, Streamlit, SQLite, pytest

**Spec Document:** `docs/superpowers/specs/2026-03-22-portfolio-to-virtual-account-design.md`

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `service/simulation_service.py` | Modify | Add `import_holdings()` method |
| `ui/pages/2_portfolio.py` | Modify | Add "发送到虚拟账户" UI block |
| `tests/service/test_simulation_service.py` | Modify | Add `TestImportHoldings` test class |

---

## Task 1: Add import_holdings() - mode validation and return structure

**Files:**
- Modify: `service/simulation_service.py`
- Modify: `tests/service/test_simulation_service.py`

- [ ] **Step 1: Write failing test for invalid mode**

Add to `tests/service/test_simulation_service.py`:

```python
class TestImportHoldings:
    """Tests for import_holdings method."""

    def setup_method(self):
        """Set up test fixtures with unique account IDs."""
        self.service = SimulationService()
        self.test_prefix = f"test_import_{uuid.uuid4().hex[:8]}"

    def _get_unique_id(self, suffix: str) -> str:
        """Generate unique account ID for test."""
        return f"{self.test_prefix}_{suffix}"

    def test_invalid_mode_raises_value_error(self):
        """Test that invalid mode raises ValueError."""
        account_id = self._get_unique_id("001")
        holdings = [{"fund_code": "000001", "fund_name": "测试基金", "amount": 10000.0}]

        with pytest.raises(ValueError, match="Invalid mode"):
            self.service.import_holdings(
                holdings=holdings,
                account_id=account_id,
                mode="invalid",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/service/test_simulation_service.py::TestImportHoldings::test_invalid_mode_raises_value_error -v`
Expected: FAIL with AttributeError or similar

- [ ] **Step 3: Add import_holdings() method skeleton with mode validation**

Add to `service/simulation_service.py` after the `execute_sell` method:

```python
    def import_holdings(
        self,
        holdings: list[dict],
        account_id: str,
        mode: str = "append",
        initial_cash: float = 0.0,
        nav: float = 1.0,
    ) -> dict:
        """Import holdings to virtual account.

        Args:
            holdings: List of holdings with fund_code, fund_name, amount
            account_id: Account identifier (required)
            mode: "append" or "replace"
            initial_cash: Initial cash for new accounts
            nav: Net value for trades (default 1.0)

        Returns:
            Dict with account, created_new_account, imported_count, etc.

        Raises:
            ValueError: If mode invalid, account not found, or insufficient cash
        """
        # Validate mode
        if mode not in ("append", "replace"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'append' or 'replace'.")

        # Calculate total amount
        total_amount = sum(h.get("amount", 0) for h in holdings)

        # Check if account exists
        account = self.get_account(account_id)
        created_new_account = account is None

        # Placeholder - will implement logic in subsequent tasks
        return {
            "account": account,
            "created_new_account": created_new_account,
            "imported_count": 0,
            "skipped_count": 0,
            "mode": mode,
            "nav_used": nav,
            "message": "Not implemented",
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/service/test_simulation_service.py::TestImportHoldings::test_invalid_mode_raises_value_error -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add service/simulation_service.py tests/service/test_simulation_service.py
git commit -m "feat(simulation): add import_holdings() method skeleton with mode validation"
```

---

## Task 2: Implement append mode

**Files:**
- Modify: `service/simulation_service.py`
- Modify: `tests/service/test_simulation_service.py`

- [ ] **Step 1: Write failing test for append mode**

Add to `TestImportHoldings` class:

```python
    def test_append_to_existing_account(self):
        """Test append mode adds to existing positions."""
        account_id = self._get_unique_id("002")
        self.service.create_account(account_id, 100000.0)

        holdings = [
            {"fund_code": "000001", "fund_name": "基金A", "amount": 10000.0},
            {"fund_code": "000002", "fund_name": "基金B", "amount": 5000.0},
        ]

        result = self.service.import_holdings(
            holdings=holdings,
            account_id=account_id,
            mode="append",
        )

        assert result["imported_count"] == 2
        assert result["created_new_account"] is False
        assert result["mode"] == "append"

        account = self.service.get_account(account_id)
        assert abs(account.cash - 85000.0) < 0.01  # 100000 - 10000 - 5000
        assert len(account.positions) == 2

    def test_append_insufficient_cash_raises(self):
        """Test append mode raises when insufficient cash."""
        account_id = self._get_unique_id("003")
        self.service.create_account(account_id, 5000.0)

        holdings = [{"fund_code": "000001", "fund_name": "基金A", "amount": 10000.0}]

        with pytest.raises(ValueError, match="Insufficient cash"):
            self.service.import_holdings(
                holdings=holdings,
                account_id=account_id,
                mode="append",
            )

    def test_append_nonexistent_account_raises(self):
        """Test append mode raises when account not found."""
        holdings = [{"fund_code": "000001", "fund_name": "基金A", "amount": 10000.0}]

        with pytest.raises(ValueError, match="Account not found"):
            self.service.import_holdings(
                holdings=holdings,
                account_id=self._get_unique_id("nonexistent"),
                mode="append",
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/service/test_simulation_service.py::TestImportHoldings -v`
Expected: FAIL (imported_count should be 0)

- [ ] **Step 3: Implement append mode logic**

Replace the placeholder in `import_holdings()`:

```python
    def import_holdings(
        self,
        holdings: list[dict],
        account_id: str,
        mode: str = "append",
        initial_cash: float = 0.0,
        nav: float = 1.0,
    ) -> dict:
        """Import holdings to virtual account.

        Args:
            holdings: List of holdings with fund_code, fund_name, amount
            account_id: Account identifier (required)
            mode: "append" or "replace"
            initial_cash: Initial cash for new accounts
            nav: Net value for trades (default 1.0)

        Returns:
            Dict with account, created_new_account, imported_count, etc.

        Raises:
            ValueError: If mode invalid, account not found, or insufficient cash
        """
        # Validate mode
        if mode not in ("append", "replace"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'append' or 'replace'.")

        # Calculate total amount
        total_amount = sum(h.get("amount", 0) for h in holdings)

        # Check if account exists
        account = self.get_account(account_id)
        created_new_account = account is None

        if mode == "append":
            return self._import_append(account_id, holdings, nav, total_amount)
        else:
            # replace mode - will implement in next task
            return self._import_replace(account_id, holdings, nav, total_amount, initial_cash, created_new_account)

    def _import_append(
        self,
        account_id: str,
        holdings: list[dict],
        nav: float,
        total_amount: float,
    ) -> dict:
        """Append holdings to existing account."""
        account = self.get_account(account_id)
        if account is None:
            raise ValueError(f"Account not found: {account_id}")

        if account.cash < total_amount:
            raise ValueError(
                f"Insufficient cash: {account.cash:.2f} < {total_amount:.2f}"
            )

        reason = "从持仓诊断页导入，按 NAV=1.0 初始化模拟持仓"
        imported_count = 0

        for h in holdings:
            self.execute_buy(
                account_id=account_id,
                fund_code=h["fund_code"],
                fund_name=h["fund_name"],
                amount=h["amount"],
                nav=nav,
                reason=reason,
            )
            imported_count += 1

        account = self.get_account(account_id)
        return {
            "account": account,
            "created_new_account": False,
            "imported_count": imported_count,
            "skipped_count": 0,
            "mode": "append",
            "nav_used": nav,
            "message": f"已将 {imported_count} 条持仓追加到账户 {account_id}",
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/service/test_simulation_service.py::TestImportHoldings -v`
Expected: PASS for append tests, FAIL for replace tests (not yet implemented)

- [ ] **Step 5: Commit**

```bash
git add service/simulation_service.py tests/service/test_simulation_service.py
git commit -m "feat(simulation): implement import_holdings append mode"
```

---

## Task 3: Implement replace mode

**Files:**
- Modify: `service/simulation_service.py`
- Modify: `tests/service/test_simulation_service.py`

- [ ] **Step 1: Write failing tests for replace mode**

Add to `TestImportHoldings` class:

```python
    def test_replace_existing_account(self):
        """Test replace mode clears old positions and adds new."""
        account_id = self._get_unique_id("004")
        self.service.create_account(account_id, 100000.0)

        # Add existing position
        self.service.execute_buy(account_id, "000099", "旧基金", 10000.0, 1.0)

        # Import new holdings
        holdings = [
            {"fund_code": "000001", "fund_name": "基金A", "amount": 20000.0},
        ]

        result = self.service.import_holdings(
            holdings=holdings,
            account_id=account_id,
            mode="replace",
        )

        assert result["imported_count"] == 1
        assert result["created_new_account"] is False

        account = self.service.get_account(account_id)
        # cash should be reset to initial_cash, then 20000 deducted
        assert abs(account.cash - 80000.0) < 0.01
        assert len(account.positions) == 1
        assert account.positions[0]["fund_code"] == "000001"

        # Old position should be gone
        assert account.get_position("000099") is None

    def test_replace_clears_trade_records(self):
        """Test replace mode clears old trade records."""
        account_id = self._get_unique_id("005")
        self.service.create_account(account_id, 100000.0)

        # Add existing trade
        self.service.execute_buy(account_id, "000099", "旧基金", 10000.0, 1.0)

        # Replace with new holdings
        holdings = [{"fund_code": "000001", "fund_name": "基金A", "amount": 5000.0}]

        self.service.import_holdings(
            holdings=holdings,
            account_id=account_id,
            mode="replace",
        )

        account = self.service.get_account(account_id)
        # Only one trade (from import)
        assert len(account.trades) == 1
        assert account.trades[0].fund_code == "000001"

    def test_replace_creates_new_account(self):
        """Test replace mode creates new account if not exists."""
        account_id = self._get_unique_id("006")

        holdings = [{"fund_code": "000001", "fund_name": "基金A", "amount": 10000.0}]

        result = self.service.import_holdings(
            holdings=holdings,
            account_id=account_id,
            mode="replace",
            initial_cash=50000.0,
        )

        assert result["imported_count"] == 1
        assert result["created_new_account"] is True

        account = self.service.get_account(account_id)
        assert account is not None
        assert abs(account.cash - 40000.0) < 0.01  # 50000 - 10000
        assert account.initial_cash == 50000.0

    def test_replace_new_account_insufficient_cash_raises(self):
        """Test replace mode raises when initial_cash insufficient."""
        account_id = self._get_unique_id("007")

        holdings = [{"fund_code": "000001", "fund_name": "基金A", "amount": 100000.0}]

        with pytest.raises(ValueError, match="Initial cash.*must be >= total amount"):
            self.service.import_holdings(
                holdings=holdings,
                account_id=account_id,
                mode="replace",
                initial_cash=50000.0,
            )

    def test_replace_empty_holdings(self):
        """Test replace with empty holdings clears account."""
        account_id = self._get_unique_id("008")
        self.service.create_account(account_id, 100000.0)
        self.service.execute_buy(account_id, "000001", "基金A", 10000.0, 1.0)

        result = self.service.import_holdings(
            holdings=[],
            account_id=account_id,
            mode="replace",
        )

        assert result["imported_count"] == 0

        account = self.service.get_account(account_id)
        assert len(account.positions) == 0
        assert len(account.trades) == 0
        assert abs(account.cash - 100000.0) < 0.01  # Reset to initial_cash
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/service/test_simulation_service.py::TestImportHoldings -v`
Expected: FAIL for replace tests

- [ ] **Step 3: Implement replace mode logic**

Add to `service/simulation_service.py`:

```python
    def _import_replace(
        self,
        account_id: str,
        holdings: list[dict],
        nav: float,
        total_amount: float,
        initial_cash: float,
        created_new_account: bool,
    ) -> dict:
        """Replace account holdings (in-memory then persist)."""
        from domain.simulation.account import buy

        # Get or create account
        account = self.get_account(account_id)

        if account is None:
            # Create new account
            if initial_cash < total_amount:
                raise ValueError(
                    f"Initial cash ({initial_cash:.2f}) must be >= total amount ({total_amount:.2f})"
                )
            account = self.create_account(account_id, initial_cash)
        else:
            # Reset to initial state (in memory)
            initial_cash = account.initial_cash

        # Clear account state in memory
        account.positions = []
        account.trades = []
        account.cash = initial_cash

        # Execute buys in memory
        reason = "从持仓诊断页导入，按 NAV=1.0 初始化模拟持仓"
        imported_count = 0

        for h in holdings:
            buy(account, h["fund_code"], h["fund_name"], h["amount"], nav, reason=reason)
            imported_count += 1

        # Persist to database (single transaction)
        self._persist_replace(account)

        return {
            "account": account,
            "created_new_account": created_new_account,
            "imported_count": imported_count,
            "skipped_count": 0,
            "mode": "replace",
            "nav_used": nav,
            "message": f"已将 {imported_count} 条持仓导入账户 {account_id}（替换模式）",
        }

    def _persist_replace(self, account: VirtualAccount) -> None:
        """Persist replace operation to database."""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Clear old data
            cursor.execute(
                "DELETE FROM virtual_account_equity_curve WHERE account_id = ?",
                (account.account_id,)
            )
            cursor.execute(
                "DELETE FROM virtual_account_position WHERE account_id = ?",
                (account.account_id,)
            )
            cursor.execute(
                "DELETE FROM trade_record WHERE account_id = ?",
                (account.account_id,)
            )

            # Update account cash
            cursor.execute(
                "UPDATE virtual_account SET cash = ? WHERE account_id = ?",
                (account.cash, account.account_id)
            )

            # Insert new positions
            for pos in account.positions:
                if isinstance(pos, dict):
                    cursor.execute("""
                        INSERT INTO virtual_account_position (
                            account_id, fund_code, fund_name, amount, weight, shares, cost_nav
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        account.account_id,
                        pos["fund_code"],
                        pos.get("fund_name", ""),
                        pos["amount"],
                        pos.get("weight", 0.0),
                        pos.get("shares"),
                        pos.get("cost_nav"),
                    ))

            # Insert new trades
            for trade in account.trades:
                cursor.execute("""
                    INSERT INTO trade_record (
                        trade_id, account_id, fund_code, action, amount, nav, shares, trade_date, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.trade_id,
                    trade.account_id,
                    trade.fund_code,
                    trade.action,
                    trade.amount,
                    trade.nav,
                    trade.shares,
                    trade.trade_date.isoformat(),
                    trade.reason,
                ))

            conn.commit()
            logger.info(f"Replaced account {account.account_id} with {len(account.positions)} positions")
        finally:
            conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/service/test_simulation_service.py::TestImportHoldings -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add service/simulation_service.py tests/service/test_simulation_service.py
git commit -m "feat(simulation): implement import_holdings replace mode"
```

---

## Task 4: Add remaining test cases

**Files:**
- Modify: `tests/service/test_simulation_service.py`

- [ ] **Step 1: Add tests for return structure and edge cases**

Add to `TestImportHoldings` class:

```python
    def test_return_structure_complete(self):
        """Test that return dict has all required keys."""
        account_id = self._get_unique_id("009")
        self.service.create_account(account_id, 100000.0)

        holdings = [{"fund_code": "000001", "fund_name": "基金A", "amount": 5000.0}]

        result = self.service.import_holdings(
            holdings=holdings,
            account_id=account_id,
            mode="append",
        )

        required_keys = [
            "account", "created_new_account", "imported_count",
            "skipped_count", "mode", "nav_used", "message"
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    @pytest.mark.xfail(reason="Known limitation: same-day same-fund append causes trade_id collision (see spec Section 八)")
    def test_append_same_fund_code_accumulates(self):
        """Test append accumulates same fund_code position.

        NOTE: This test is expected to FAIL due to a known limitation.
        The domain layer's _generate_trade_id() creates duplicate IDs for
        same-day same-fund trades, causing IntegrityError on the second import.
        See spec Section 八: "同日同基金追加 trade_id 冲突"
        """
        account_id = self._get_unique_id("010")
        self.service.create_account(account_id, 100000.0)

        # First import
        holdings = [{"fund_code": "000001", "fund_name": "基金A", "amount": 5000.0}]
        self.service.import_holdings(holdings=holdings, account_id=account_id, mode="append")

        # Second import same fund - will fail with IntegrityError
        self.service.import_holdings(holdings=holdings, account_id=account_id, mode="append")

        account = self.service.get_account(account_id)
        assert len(account.positions) == 1
        assert abs(account.positions[0]["amount"] - 10000.0) < 0.01

    def test_append_different_fund_codes_succeeds(self):
        """Test append with different fund_codes succeeds on same day."""
        account_id = self._get_unique_id("010b")
        self.service.create_account(account_id, 100000.0)

        # Import different funds
        holdings = [
            {"fund_code": "000001", "fund_name": "基金A", "amount": 5000.0},
            {"fund_code": "000002", "fund_name": "基金B", "amount": 3000.0},
        ]

        result = self.service.import_holdings(
            holdings=holdings, account_id=account_id, mode="append"
        )

        assert result["imported_count"] == 2
        account = self.service.get_account(account_id)
        assert len(account.positions) == 2

    def test_append_empty_holdings(self):
        """Test append with empty holdings does nothing."""
        account_id = self._get_unique_id("011")
        self.service.create_account(account_id, 100000.0)

        result = self.service.import_holdings(
            holdings=[],
            account_id=account_id,
            mode="append",
        )

        assert result["imported_count"] == 0
        account = self.service.get_account(account_id)
        assert abs(account.cash - 100000.0) < 0.01

    def test_replace_same_day_twice_succeeds(self):
        """Test replace twice on same day succeeds (trade_id cleared each time)."""
        account_id = self._get_unique_id("012")
        self.service.create_account(account_id, 100000.0)

        holdings = [{"fund_code": "000001", "fund_name": "基金A", "amount": 5000.0}]

        # First replace
        result1 = self.service.import_holdings(
            holdings=holdings, account_id=account_id, mode="replace"
        )
        assert result1["imported_count"] == 1

        # Second replace same day
        result2 = self.service.import_holdings(
            holdings=holdings, account_id=account_id, mode="replace"
        )
        assert result2["imported_count"] == 1

        # Should have only one trade record
        account = self.service.get_account(account_id)
        assert len(account.trades) == 1
```

- [ ] **Step 2: Run all tests**

Run: `uv run pytest tests/service/test_simulation_service.py::TestImportHoldings -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/service/test_simulation_service.py
git commit -m "test(simulation): add edge case tests for import_holdings"
```

---

## Task 5: Add UI block to portfolio page

**Files:**
- Modify: `ui/pages/2_portfolio.py`

- [ ] **Step 1: Add "发送到虚拟账户" expander block**

Add after the "清空持仓" button section in `ui/pages/2_portfolio.py`:

```python
    # -----------------------------------------------------------------------
    # Send to Virtual Account Section
    # -----------------------------------------------------------------------
    st.divider()

    # Only show when holdings exist (spec Section 五: 显示条件)
    if st.session_state.holdings:
        total_import_amount = sum(h["amount"] for h in st.session_state.holdings)

        with st.expander("📤 发送到虚拟账户", expanded=False):
            st.info("⚠️ 所有持仓将按 NAV=1.0 建仓，仅用于建立模拟起点，不代表真实持仓成本。")

            col_left, col_right = st.columns(2)
            with col_left:
                account_type = st.radio(
                    "目标账户类型",
                    options=["新建账户", "已有账户"],
                    horizontal=True,
                    key="va_account_type",
                )

            if account_type == "新建账户":
                new_account_id = st.text_input(
                    "账户 ID",
                    placeholder="输入新账户 ID",
                    key="va_new_account_id",
                )
                min_cash = total_import_amount
                initial_cash_input = st.number_input(
                    "初始资金",
                    min_value=float(min_cash),
                    value=float(min_cash),
                    step=10000.0,
                    key="va_initial_cash",
                )
                mode = "replace"  # New account always uses replace
            else:
                existing_account_id = st.text_input(
                    "账户 ID",
                    placeholder="输入已有账户 ID",
                    key="va_existing_account_id",
                )
                mode = st.radio(
                    "导入模式",
                    options=["追加到现有持仓", "替换现有持仓"],
                    horizontal=True,
                    key="va_import_mode",
                )
                mode = "append" if mode == "追加到现有持仓" else "replace"

            if st.button("确认导入", type="primary", key="btn_import_to_va"):
                from service.simulation_service import SimulationService as SimService

                va_service = SimService()

                # Determine account_id based on type
                if account_type == "新建账户":
                    account_id = new_account_id
                    initial_cash = initial_cash_input
                else:
                    account_id = existing_account_id
                    initial_cash = 0.0  # Not used for existing account

                # Validate account_id
                if not account_id or not account_id.strip():
                    st.warning("请输入账户 ID")
                else:
                    try:
                        result = va_service.import_holdings(
                            holdings=st.session_state.holdings,
                            account_id=account_id,
                            mode=mode,
                            initial_cash=initial_cash,
                            nav=1.0,
                        )

                        st.success(
                            f"✅ 已将 {result['imported_count']} 条持仓导入账户 {account_id}（模式：{mode}）"
                        )
                        st.page_link("pages/3_strategy_lab.py", label="前往策略验证页查看 →")

                    except ValueError as e:
                        error_msg = str(e)
                        if "Account not found" in error_msg:
                            st.error(f"未找到账户 {account_id}，请先在策略验证页创建账户")
                        elif "Insufficient cash" in error_msg:
                            account = va_service.get_account(account_id)
                            current_cash = account.cash if account else 0
                            needed = total_import_amount
                            st.error(f"账户余额不足，无法追加导入。当前余额：¥{current_cash:,.0f}，需要：¥{needed:,.0f}")
                        elif "Initial cash" in error_msg:
                            st.error(f"初始资金必须 ≥ 持仓总金额 ¥{total_import_amount:,.0f}")
                        else:
                            st.error(f"导入失败：{error_msg}")
```

- [ ] **Step 2: Verify UI loads correctly**

Run: `uv run streamlit run ui/app.py`
Expected: UI loads without errors

- [ ] **Step 3: Manual test**

1. Add some holdings in the portfolio page
2. Expand "发送到虚拟账户"
3. Test creating a new account with replace
4. Test appending to existing account
5. Verify success/error messages display correctly

- [ ] **Step 4: Commit**

```bash
git add ui/pages/2_portfolio.py
git commit -m "feat(ui): add '发送到虚拟账户' block to portfolio page"
```

---

## Task 6: Final verification and integration

**Files:**
- No file changes

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run linting/type checking (if configured)**

Run: `uv run ruff check .` or similar
Expected: No errors

- [ ] **Step 3: Manual integration test**

1. Run `uv run streamlit run ui/app.py`
2. Go to portfolio page
3. Import or add holdings
4. Send to virtual account (new account)
5. Verify account appears in strategy lab
6. Send more holdings (append mode)
7. Verify positions accumulated
8. Send holdings (replace mode)
9. Verify old positions cleared

- [ ] **Step 4: Update project status**

Update `docs/project_status.md` to mark "持仓导入 → 虚拟账户" as completed.

- [ ] **Step 5: Final commit**

```bash
git add docs/project_status.md
git commit -m "docs: mark 持仓导入到虚拟账户 as completed"
```

---

## Summary

| Task | Files Changed | Tests Added |
|------|---------------|-------------|
| 1. Mode validation | `simulation_service.py`, `test_simulation_service.py` | 1 |
| 2. Append mode | `simulation_service.py`, `test_simulation_service.py` | 3 |
| 3. Replace mode | `simulation_service.py`, `test_simulation_service.py` | 5 |
| 4. Edge cases | `test_simulation_service.py` | 4 |
| 5. UI block | `2_portfolio.py` | - |
| 6. Integration | - | - |

**Total new tests:** 13