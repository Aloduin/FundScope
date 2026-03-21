"""Tests for virtual account trading."""
from datetime import date, timedelta
import pytest
from domain.simulation.models import VirtualAccount
from domain.simulation.account import buy, sell


class TestVirtualAccount:
    """Tests for VirtualAccount dataclass."""

    def test_create_account_with_defaults(self):
        """Test creating account with default values."""
        account = VirtualAccount(
            account_id="acc_001",
            initial_cash=100000.0,
            cash=100000.0,
        )

        assert account.account_id == "acc_001"
        assert account.initial_cash == 100000.0
        assert account.cash == 100000.0
        assert account.positions == []
        assert account.trades == []
        assert account.created_at is not None

    def test_post_init_initializes_equity_curve(self):
        """Test that __post_init__ initializes equity_curve."""
        account = VirtualAccount(
            account_id="acc_001",
            initial_cash=100000.0,
            cash=100000.0,
        )

        assert account.equity_curve is not None
        assert len(account.equity_curve) >= 1

    def test_get_position_existing(self):
        """Test getting existing position."""
        account = VirtualAccount(account_id="acc_001", initial_cash=100000.0, cash=100000.0)
        account.positions.append({"fund_code": "000001", "fund_name": "基金 1", "amount": 10000.0, "shares": 100.0})

        pos = account.get_position("000001")

        assert pos is not None
        assert pos["fund_code"] == "000001"

    def test_get_position_nonexistent(self):
        """Test getting nonexistent position."""
        account = VirtualAccount(account_id="acc_001", initial_cash=100000.0, cash=100000.0)

        pos = account.get_position("999999")

        assert pos is None


class TestBuy:
    """Tests for buy function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.account = VirtualAccount(
            account_id="acc_001",
            initial_cash=100000.0,
            cash=100000.0,
        )

    def test_buy_success(self):
        """Test successful buy."""
        trade = buy(
            self.account,
            fund_code="000001",
            fund_name="测试基金",
            amount=10000.0,
            nav=1.0,
        )

        assert trade is not None
        assert trade.account_id == "acc_001"
        assert trade.fund_code == "000001"
        assert trade.action == "BUY"
        assert abs(trade.amount - 10000.0) < 0.01
        assert abs(trade.shares - 10000.0) < 0.01

    def test_buy_updates_cash(self):
        """Test that buy updates cash."""
        buy(self.account, fund_code="000001", fund_name="测试基金", amount=10000.0, nav=1.0)

        assert abs(self.account.cash - 90000.0) < 0.01

    def test_buy_creates_position(self):
        """Test that buy creates position."""
        buy(self.account, fund_code="000001", fund_name="测试基金", amount=10000.0, nav=1.0)

        pos = self.account.get_position("000001")
        assert pos is not None
        assert abs(pos["amount"] - 10000.0) < 0.01
        assert abs(pos["shares"] - 10000.0) < 0.01
        assert pos["cost_nav"] == 1.0

    def test_buy_insufficient_cash_raises(self):
        """Test that buy with insufficient cash raises."""
        with pytest.raises(ValueError, match="Insufficient cash"):
            buy(self.account, fund_code="000001", fund_name="测试基金", amount=200000.0, nav=1.0)

    def test_buy_trade_has_account_id(self):
        """Test that trade record has account_id."""
        trade = buy(self.account, fund_code="000001", fund_name="测试基金", amount=10000.0, nav=1.0)

        assert trade.account_id == "acc_001"


class TestSell:
    """Tests for sell function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.account = VirtualAccount(
            account_id="acc_001",
            initial_cash=100000.0,
            cash=100000.0,
        )
        # Initial buy
        buy(self.account, fund_code="000001", fund_name="测试基金", amount=10000.0, nav=1.0)

    def test_sell_success(self):
        """Test successful sell."""
        trade = sell(
            self.account,
            fund_code="000001",
            fund_name="测试基金",
            amount=5000.0,
            nav=1.0,
        )

        assert trade is not None
        assert trade.account_id == "acc_001"
        assert trade.fund_code == "000001"
        assert trade.action == "SELL"

    def test_sell_updates_cash(self):
        """Test that sell updates cash."""
        # Initial: cash=100000, buy 10000 -> cash=90000, sell 5000 -> cash=95000
        sell(self.account, fund_code="000001", fund_name="测试基金", amount=5000.0, nav=1.0)

        assert abs(self.account.cash - 95000.0) < 0.01

    def test_sell_reduces_position(self):
        """Test that sell reduces position."""
        sell(self.account, fund_code="000001", fund_name="测试基金", amount=5000.0, nav=1.0)

        pos = self.account.get_position("000001")
        assert pos is not None
        assert abs(pos["amount"] - 5000.0) < 0.01

    def test_sell_no_position_raises(self):
        """Test that sell with no position raises."""
        with pytest.raises(ValueError, match="No position"):
            sell(self.account, fund_code="999999", fund_name="不存在", amount=1000.0, nav=1.0)

    def test_sell_insufficient_shares_raises(self):
        """Test that sell with insufficient shares raises."""
        with pytest.raises(ValueError, match="Insufficient shares"):
            sell(self.account, fund_code="000001", fund_name="测试基金", amount=20000.0, nav=1.0)

    def test_sell_trade_has_account_id(self):
        """Test that trade record has account_id."""
        trade = sell(self.account, fund_code="000001", fund_name="测试基金", amount=5000.0, nav=1.0)

        assert trade.account_id == "acc_001"


class TestGetTotalEquity:
    """Tests for get_total_equity method."""

    def test_equity_with_cash_only(self):
        """Test equity with cash only."""
        account = VirtualAccount(account_id="acc_001", initial_cash=100000.0, cash=100000.0)

        equity = account.get_total_equity({})

        assert abs(equity - 100000.0) < 0.01

    def test_equity_with_positions(self):
        """Test equity with positions."""
        account = VirtualAccount(account_id="acc_001", initial_cash=50000.0, cash=50000.0)
        account.add_position("000001", "基金 1", 50000.0, 1.0, 50000.0)

        # NAV increased to 1.1
        equity = account.get_total_equity({"000001": 1.1})

        # Cash 50000 + shares 50000 * nav 1.1 = 105000
        assert abs(equity - 105000.0) < 0.01

    def test_equity_uses_cost_nav_if_not_in_map(self):
        """Test equity uses cost_nav if fund not in nav_map."""
        account = VirtualAccount(account_id="acc_001", initial_cash=50000.0, cash=50000.0)
        account.add_position("000001", "基金 1", 50000.0, 1.0, 50000.0)

        # Empty nav_map should use cost_nav
        equity = account.get_total_equity({})

        # Cash 50000 + shares 50000 * cost_nav 1.0 = 100000
        assert abs(equity - 100000.0) < 0.01
