"""Tests for simulation service."""
import pytest
import uuid
from service.simulation_service import SimulationService
from domain.simulation.models import VirtualAccount


class TestSimulationService:
    """Tests for SimulationService."""

    def setup_method(self):
        """Set up test fixtures with unique account IDs."""
        self.service = SimulationService()
        self.test_prefix = f"test_{uuid.uuid4().hex[:8]}"

    def _get_unique_id(self, suffix: str) -> str:
        """Generate unique account ID for test."""
        return f"{self.test_prefix}_{suffix}"

    def test_create_account_returns_account(self):
        """Test create_account returns VirtualAccount."""
        account_id = self._get_unique_id("001")
        account = self.service.create_account(account_id, 100000.0)

        assert isinstance(account, VirtualAccount)
        assert account.account_id == account_id
        assert account.initial_cash == 100000.0
        assert account.cash == 100000.0

    def test_get_account_after_create(self):
        """Test get_account returns account after creation."""
        account_id = self._get_unique_id("002")
        self.service.create_account(account_id, 50000.0)

        account = self.service.get_account(account_id)

        assert account is not None
        assert account.account_id == account_id
        assert account.initial_cash == 50000.0

    def test_get_account_nonexistent(self):
        """Test get_account returns None for nonexistent account."""
        account = self.service.get_account(self._get_unique_id("nonexistent"))

        assert account is None

    def test_execute_buy_success(self):
        """Test execute_buy executes successfully."""
        account_id = self._get_unique_id("003")
        self.service.create_account(account_id, 100000.0)

        trade = self.service.execute_buy(
            account_id,
            fund_code="000001",
            fund_name="测试基金",
            amount=10000.0,
            nav=1.0,
        )

        assert trade is not None
        assert trade.account_id == account_id
        assert trade.fund_code == "000001"
        assert trade.action == "BUY"

    def test_execute_buy_updates_cash(self):
        """Test execute_buy updates account cash."""
        account_id = self._get_unique_id("004")
        self.service.create_account(account_id, 100000.0)

        self.service.execute_buy(
            account_id,
            fund_code="000001",
            fund_name="测试基金",
            amount=10000.0,
            nav=1.0,
        )

        account = self.service.get_account(account_id)
        assert abs(account.cash - 90000.0) < 0.01

    def test_execute_buy_creates_position(self):
        """Test execute_buy creates position."""
        account_id = self._get_unique_id("005")
        self.service.create_account(account_id, 100000.0)

        self.service.execute_buy(
            account_id,
            fund_code="000001",
            fund_name="测试基金",
            amount=10000.0,
            nav=1.0,
        )

        account = self.service.get_account(account_id)
        position = account.get_position("000001")

        assert position is not None
        assert abs(position["amount"] - 10000.0) < 0.01

    def test_execute_sell_success(self):
        """Test execute_sell executes successfully."""
        account_id = self._get_unique_id("006")
        self.service.create_account(account_id, 100000.0)
        self.service.execute_buy(account_id, "000001", "测试基金", 10000.0, 1.0)

        trade = self.service.execute_sell(
            account_id,
            fund_code="000001",
            fund_name="测试基金",
            amount=5000.0,
            nav=1.0,
        )

        assert trade is not None
        assert trade.action == "SELL"

    def test_execute_sell_updates_cash(self):
        """Test execute_sell updates account cash."""
        account_id = self._get_unique_id("007")
        self.service.create_account(account_id, 100000.0)
        self.service.execute_buy(account_id, "000001", "测试基金", 10000.0, 1.0)

        self.service.execute_sell(
            account_id,
            fund_code="000001",
            fund_name="测试基金",
            amount=5000.0,
            nav=1.0,
        )

        account = self.service.get_account(account_id)
        # Initial 100000 - buy 10000 + sell 5000 = 95000
        assert abs(account.cash - 95000.0) < 0.01

    def test_execute_buy_nonexistent_account_raises(self):
        """Test execute_buy raises for nonexistent account."""
        with pytest.raises(ValueError, match="Account not found"):
            self.service.execute_buy(
                self._get_unique_id("nonexistent"),
                fund_code="000001",
                fund_name="测试基金",
                amount=10000.0,
                nav=1.0,
            )

    def test_trades_persisted(self):
        """Test that trades are persisted to database."""
        account_id = self._get_unique_id("008")
        self.service.create_account(account_id, 100000.0)
        self.service.execute_buy(account_id, "000001", "测试基金", 10000.0, 1.0)

        account = self.service.get_account(account_id)

        assert len(account.trades) >= 1
        assert account.trades[0].action == "BUY"
        assert account.trades[0].account_id == account_id


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
